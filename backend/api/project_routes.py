"""
Project (Smart Folder) API Routes
Endpoints for creating smart folders that auto-populate with semantically similar documents.
"""

from flask import Blueprint, request, jsonify, g
from database.models import SessionLocal, Project, Document, utc_now
from services.auth_service import require_auth
from services.openai_client import get_openai_client

project_bp = Blueprint('project', __name__)

# Pinecone store singleton
_vector_store = None


def _get_vector_store():
    """Lazy-load the Pinecone vector store."""
    global _vector_store
    if _vector_store is None:
        try:
            from vector_stores.pinecone_store import PineconeVectorStore
            _vector_store = PineconeVectorStore()
        except Exception as e:
            print(f"[ProjectRoutes] Could not initialize Pinecone: {e}")
            return None
    return _vector_store


@project_bp.route('/api/projects', methods=['GET'])
@require_auth
def list_projects():
    """List all smart folders for the current tenant."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        projects = (
            db.query(Project)
            .filter(Project.tenant_id == tenant_id, Project.is_archived == False)
            .order_by(Project.created_at.desc())
            .all()
        )

        result = []
        for p in projects:
            data = p.to_dict()
            # Include actual document IDs for frontend filtering
            doc_ids = [
                d.id for d in
                db.query(Document.id)
                .filter(Document.project_id == p.id, Document.tenant_id == tenant_id)
                .all()
            ]
            data['document_ids'] = doc_ids
            data['document_count'] = len(doc_ids)
            result.append(data)

        return jsonify({"success": True, "projects": result})
    except Exception as e:
        print(f"[ProjectRoutes] Error listing projects: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@project_bp.route('/api/projects/smart-create', methods=['POST'])
@require_auth
def smart_create_project():
    """
    Create a smart folder and return semantically matched document candidates.

    Request body:
        name: str - folder name
        description: str - short description of what belongs in this folder
        color: str - hex color code (e.g. '#B8A394')

    Returns:
        project: the created project
        candidates: list of matched documents with similarity scores
    """
    tenant_id = g.tenant_id
    data = request.get_json()

    name = (data.get('name') or '').strip()
    description = (data.get('description') or '').strip()
    color = data.get('color', '#B8A394')

    if not name:
        return jsonify({"error": "Folder name is required"}), 400

    db = SessionLocal()
    try:
        # 1. Create the project in DB
        project = Project(
            tenant_id=tenant_id,
            name=name,
            description=description,
            color=color,
            is_auto_generated=False,
            document_count=0,
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # 2. Embed the folder query text
        query_text = f"{name}. {description}" if description else name
        vector_store = _get_vector_store()

        candidates = []
        if vector_store:
            try:
                # Search Pinecone for semantically similar documents
                results = vector_store.search(
                    query=query_text,
                    tenant_id=tenant_id,
                    top_k=60,  # Get more chunks, deduplicate to ~20-30 docs
                )

                # Deduplicate chunks to document level, averaging scores
                doc_scores = {}
                for r in results:
                    doc_id = r.get('doc_id', '')
                    if not doc_id:
                        continue
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = {'scores': [], 'title': r.get('title', '')}
                    doc_scores[doc_id]['scores'].append(r.get('score', 0))

                # Average scores and sort
                scored_docs = []
                for doc_id, info in doc_scores.items():
                    avg_score = sum(info['scores']) / len(info['scores'])
                    scored_docs.append({
                        'doc_id': doc_id,
                        'score': round(avg_score, 4),
                        'title': info['title'],
                    })

                scored_docs.sort(key=lambda x: x['score'], reverse=True)

                # Fetch full document metadata for top candidates
                top_doc_ids = [d['doc_id'] for d in scored_docs[:30]]
                if top_doc_ids:
                    docs = (
                        db.query(Document)
                        .filter(
                            Document.id.in_(top_doc_ids),
                            Document.tenant_id == tenant_id,
                        )
                        .all()
                    )
                    doc_map = {d.id: d for d in docs}

                    for sd in scored_docs[:30]:
                        doc = doc_map.get(sd['doc_id'])
                        if doc:
                            candidates.append({
                                'id': doc.id,
                                'name': doc.title or doc.original_filename or 'Untitled',
                                'source_type': doc.source_type,
                                'classification': doc.classification.value if doc.classification else None,
                                'created_at': doc.created_at.isoformat() if doc.created_at else None,
                                'score': sd['score'],
                            })
            except Exception as e:
                print(f"[ProjectRoutes] Pinecone search failed: {e}")
                import traceback
                traceback.print_exc()

        return jsonify({
            "success": True,
            "project": project.to_dict(),
            "candidates": candidates,
        })

    except Exception as e:
        db.rollback()
        print(f"[ProjectRoutes] Error creating smart folder: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@project_bp.route('/api/projects/<project_id>/confirm', methods=['POST'])
@require_auth
def confirm_project_documents(project_id):
    """
    Assign selected documents to the project.

    Request body:
        document_ids: list of document IDs to add to the folder
    """
    tenant_id = g.tenant_id
    data = request.get_json()
    document_ids = data.get('document_ids', [])

    if not document_ids:
        return jsonify({"error": "No documents selected"}), 400

    db = SessionLocal()
    try:
        # Verify project belongs to tenant
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.tenant_id == tenant_id)
            .first()
        )
        if not project:
            return jsonify({"error": "Folder not found"}), 404

        # Assign documents to this project
        updated = (
            db.query(Document)
            .filter(
                Document.id.in_(document_ids),
                Document.tenant_id == tenant_id,
            )
            .update({Document.project_id: project_id}, synchronize_session='fetch')
        )

        project.document_count = updated
        project.updated_at = utc_now()
        db.commit()

        # Return updated project with doc IDs
        result = project.to_dict()
        result['document_ids'] = document_ids
        result['document_count'] = updated

        return jsonify({"success": True, "project": result})

    except Exception as e:
        db.rollback()
        print(f"[ProjectRoutes] Error confirming documents: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@project_bp.route('/api/projects/<project_id>', methods=['DELETE'])
@require_auth
def delete_project(project_id):
    """Delete a smart folder and unset project_id on its documents."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        project = (
            db.query(Project)
            .filter(Project.id == project_id, Project.tenant_id == tenant_id)
            .first()
        )
        if not project:
            return jsonify({"error": "Folder not found"}), 404

        # Unset project_id on documents
        db.query(Document).filter(
            Document.project_id == project_id,
            Document.tenant_id == tenant_id,
        ).update({Document.project_id: None}, synchronize_session='fetch')

        db.delete(project)
        db.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        print(f"[ProjectRoutes] Error deleting folder: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@project_bp.route('/api/projects/<project_id>/documents/<doc_id>', methods=['DELETE'])
@require_auth
def remove_document_from_project(project_id, doc_id):
    """Remove a single document from a folder."""
    tenant_id = g.tenant_id
    db = SessionLocal()
    try:
        doc = (
            db.query(Document)
            .filter(
                Document.id == doc_id,
                Document.project_id == project_id,
                Document.tenant_id == tenant_id,
            )
            .first()
        )
        if not doc:
            return jsonify({"error": "Document not found in folder"}), 404

        doc.project_id = None
        doc.updated_at = utc_now()

        # Update project count
        project = db.query(Project).filter(Project.id == project_id).first()
        if project:
            count = db.query(Document).filter(Document.project_id == project_id).count()
            project.document_count = count

        db.commit()

        return jsonify({"success": True})

    except Exception as e:
        db.rollback()
        print(f"[ProjectRoutes] Error removing document: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
