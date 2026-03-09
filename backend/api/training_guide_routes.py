"""
Training Guide API Routes
Endpoints for creating, confirming, and managing training guides
generated via NotebookLM from the user's knowledge base.
"""

import os
import logging
from flask import Blueprint, request, jsonify, g, redirect, send_file

from database.models import (
    SessionLocal, TrainingGuide, TrainingGuideStatus, Document, DocumentStatus, utc_now
)
from services.auth_service import require_auth
from services.notebooklm_service import get_notebooklm_service

logger = logging.getLogger(__name__)

training_guide_bp = Blueprint('training_guides', __name__, url_prefix='/api/training-guides')


def get_db():
    return SessionLocal()


# ============================================================================
# GENERATE OUTLINE
# ============================================================================

@training_guide_bp.route('/outline', methods=['POST'])
@require_auth
def generate_outline():
    """
    Step 1: Select documents and generate a content outline.
    Creates a TrainingGuide in DRAFT status with an LLM-generated outline.

    Body: { title, description?, source_document_ids: [...], video_style?, instructions? }
    """
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({"error": "Title is required"}), 400

    doc_ids = data.get('source_document_ids', [])
    if not doc_ids:
        return jsonify({"error": "At least one source document is required"}), 400

    db = get_db()
    try:
        # Verify documents exist and belong to tenant
        docs = db.query(Document).filter(
            Document.id.in_(doc_ids),
            Document.tenant_id == g.tenant_id,
        ).all()

        if not docs:
            return jsonify({"error": "No valid documents found"}), 404

        # Generate outline from document content using Azure OpenAI
        outline = _generate_outline_from_docs(docs, title, data.get('instructions'))

        # Create training guide in DRAFT status
        guide = TrainingGuide(
            tenant_id=g.tenant_id,
            title=title,
            description=data.get('description', ''),
            source_document_ids=[d.id for d in docs],
            content_outline=outline,
            instructions=data.get('instructions'),
            video_style=data.get('video_style', 'classic'),
            video_format=data.get('video_format', 'explainer'),
            slide_format=data.get('slide_format', 'detailed_deck'),
            status=TrainingGuideStatus.DRAFT,
        )
        db.add(guide)
        db.commit()

        return jsonify({
            "guide": guide.to_dict(),
            "documents_found": len(docs),
            "documents_requested": len(doc_ids),
        }), 201

    except Exception as e:
        logger.error(f"Outline generation error: {e}", exc_info=True)
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


def _generate_outline_from_docs(docs, title: str, instructions: str = None) -> str:
    """Use Azure OpenAI to generate a content outline from document summaries."""
    try:
        from services.openai_client import get_openai_client
        client = get_openai_client()

        # Build document context (use summaries when available, truncate raw content)
        doc_summaries = []
        for doc in docs[:20]:  # Max 20 docs
            if doc.structured_summary and isinstance(doc.structured_summary, dict):
                summary = doc.structured_summary.get('summary', '')
                topics = doc.structured_summary.get('key_topics', [])
                doc_summaries.append(
                    f"**{doc.title}**: {summary}\n  Topics: {', '.join(topics[:5])}"
                )
            elif doc.content:
                doc_summaries.append(
                    f"**{doc.title}**: {doc.content[:500]}..."
                )

        docs_text = "\n\n".join(doc_summaries)

        system_prompt = (
            "You are a training content designer. Generate a clear, structured outline "
            "for a training video and slide deck based on the provided documents. "
            "The outline should be practical and educational."
        )

        user_prompt = f"""Create a training content outline for: "{title}"

Based on these knowledge base documents:
{docs_text}

{f'Additional instructions: {instructions}' if instructions else ''}

Generate a structured outline with:
1. Introduction — what this training covers and why it matters
2. 3-6 main sections — each with 2-4 key points
3. Summary — key takeaways

Format as a clean numbered outline. Keep it concise but comprehensive."""

        response = client.chat.completions.create(
            model=os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"Outline generation via LLM failed: {e}")
        # Fallback: simple outline from doc titles
        lines = [f"Training: {title}", "", "Topics covered:"]
        for i, doc in enumerate(docs[:10], 1):
            lines.append(f"  {i}. {doc.title}")
        return "\n".join(lines)


# ============================================================================
# AUTO-SUGGEST IDEAS
# ============================================================================

@training_guide_bp.route('/suggest-ideas', methods=['POST'])
@require_auth
def suggest_ideas():
    """
    Analyze the user's knowledge base and auto-generate training video ideas.
    Each idea includes a title, description, and suggested document IDs.
    """
    db = get_db()
    try:
        # Fetch all non-rejected documents (includes pending, classified, confirmed)
        docs = db.query(Document).filter(
            Document.tenant_id == g.tenant_id,
            Document.status.notin_([DocumentStatus.REJECTED, DocumentStatus.ARCHIVED]),
        ).order_by(Document.created_at.desc()).limit(100).all()

        if not docs:
            return jsonify({"ideas": [], "message": "No documents in knowledge base yet"}), 200

        # Build document summaries for LLM
        doc_entries = []
        for doc in docs:
            summary = ""
            topics = []
            if doc.structured_summary and isinstance(doc.structured_summary, dict):
                summary = doc.structured_summary.get('summary', '')
                topics = doc.structured_summary.get('key_topics', [])
            elif doc.content:
                summary = doc.content[:300]
            doc_entries.append({
                "id": doc.id,
                "title": doc.title or "Untitled",
                "summary": summary,
                "topics": topics,
            })

        # Call LLM to generate ideas
        ideas = _generate_ideas_from_docs(doc_entries)

        return jsonify({"ideas": ideas, "total_documents": len(docs)})

    except Exception as e:
        logger.error(f"Suggest ideas error: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


def _generate_ideas_from_docs(doc_entries: list) -> list:
    """Use LLM to cluster documents and propose training video ideas."""
    try:
        from services.openai_client import get_openai_client
        client = get_openai_client()

        docs_text = "\n".join([
            f"- [{d['id'][:8]}] {d['title']}: {d['summary'][:200]}"
            + (f" (Topics: {', '.join(d['topics'][:3])})" if d['topics'] else "")
            for d in doc_entries[:60]
        ])

        response = client.chat.completions.create(
            model=os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-4o"),
            messages=[
                {"role": "system", "content": (
                    "You analyze a knowledge base and suggest training video ideas. "
                    "Return valid JSON only — an array of idea objects."
                )},
                {"role": "user", "content": f"""Analyze these knowledge base documents and suggest 4-6 training video ideas.
Each idea should group related documents into a coherent training topic.

Documents:
{docs_text}

Return a JSON array where each idea has:
- "title": concise training title (e.g. "Lab Safety Protocols Overview")
- "description": 1-2 sentence description of what the training covers
- "document_ids": array of document ID prefixes (the 8-char codes in brackets) that should be included
- "suggested_outline": brief 3-5 point outline of what the video should cover

Only return the JSON array, no other text."""},
            ],
            max_tokens=2000,
            temperature=0.7,
            response_format={"type": "json_object"},
        )

        import json
        result = json.loads(response.choices[0].message.content)
        ideas = result if isinstance(result, list) else result.get("ideas", result.get("suggestions", []))

        # Map 8-char ID prefixes back to full document IDs
        for idea in ideas:
            full_ids = []
            for prefix in idea.get("document_ids", []):
                for d in doc_entries:
                    if d["id"].startswith(prefix):
                        full_ids.append(d["id"])
                        break
            idea["document_ids"] = full_ids
            # Include document titles for display
            idea["documents"] = [
                {"id": d["id"], "title": d["title"]}
                for d in doc_entries if d["id"] in full_ids
            ]

        return ideas

    except Exception as e:
        logger.error(f"Idea generation failed: {e}", exc_info=True)
        # Fallback: group by recent uploads
        return [{
            "title": "Recent Knowledge Base Overview",
            "description": "A training overview of your recently added documents",
            "document_ids": [d["id"] for d in doc_entries[:10]],
            "documents": [{"id": d["id"], "title": d["title"]} for d in doc_entries[:10]],
            "suggested_outline": "1. Introduction\n2. Key topics covered\n3. Important findings\n4. Next steps",
        }]


# ============================================================================
# CONFIRM & GENERATE
# ============================================================================

@training_guide_bp.route('/<guide_id>/confirm', methods=['POST'])
@require_auth
def confirm_and_generate(guide_id):
    """
    Step 2: User confirms (and optionally edits) the outline, triggers generation.
    Body: { content_outline?, instructions?, video_style?, video_format?, slide_format? }
    """
    service = get_notebooklm_service()
    if not service.is_available:
        return jsonify({"error": "NotebookLM service is not configured"}), 503

    data = request.get_json() or {}
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()

        if not guide:
            return jsonify({"error": "Training guide not found"}), 404

        if guide.status != TrainingGuideStatus.DRAFT:
            return jsonify({"error": f"Guide is in '{guide.status.value}' state, not draft"}), 400

        # Allow user to update outline and settings
        if 'content_outline' in data:
            guide.content_outline = data['content_outline']
        if 'instructions' in data:
            guide.instructions = data['instructions']
        if 'video_style' in data:
            guide.video_style = data['video_style']
        if 'video_format' in data:
            guide.video_format = data['video_format']
        if 'slide_format' in data:
            guide.slide_format = data['slide_format']

        guide.confirmed_at = utc_now()
        guide.status = TrainingGuideStatus.GENERATING
        guide.progress_percent = 0
        guide.current_step = "Queued for generation..."
        db.commit()

        # Kick off background generation
        service.generate_content_async(guide.id, g.tenant_id)

        return jsonify({
            "guide": guide.to_dict(),
            "message": "Generation started. Poll /status for progress.",
        })

    except Exception as e:
        logger.error(f"Confirm error: {e}", exc_info=True)
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# LIST & GET
# ============================================================================

@training_guide_bp.route('', methods=['GET'])
@require_auth
def list_guides():
    """List all training guides for the tenant."""
    db = get_db()
    try:
        status = request.args.get('status')
        limit = min(int(request.args.get('limit', 50)), 100)
        offset = int(request.args.get('offset', 0))

        query = db.query(TrainingGuide).filter_by(tenant_id=g.tenant_id)

        if status:
            try:
                status_enum = TrainingGuideStatus(status)
                query = query.filter_by(status=status_enum)
            except ValueError:
                pass

        total = query.count()
        guides = query.order_by(TrainingGuide.created_at.desc()).offset(offset).limit(limit).all()

        return jsonify({
            "guides": [g.to_dict() for g in guides],
            "total": total,
            "limit": limit,
            "offset": offset,
        })
    finally:
        db.close()


@training_guide_bp.route('/<guide_id>', methods=['GET'])
@require_auth
def get_guide(guide_id):
    """Get a single training guide."""
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404
        return jsonify({"guide": guide.to_dict()})
    finally:
        db.close()


# ============================================================================
# STATUS POLLING
# ============================================================================

@training_guide_bp.route('/<guide_id>/status', methods=['GET'])
@require_auth
def get_guide_status(guide_id):
    """Poll generation progress."""
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404
        return jsonify({
            "id": guide.id,
            "status": guide.status.value,
            "progress_percent": guide.progress_percent,
            "current_step": guide.current_step,
            "error_message": guide.error_message,
            "video_path": guide.video_path,
            "slides_path": guide.slides_path,
            "slides_pdf_path": guide.slides_pdf_path,
        })
    finally:
        db.close()


# ============================================================================
# DOWNLOADS
# ============================================================================

@training_guide_bp.route('/<guide_id>/video', methods=['GET'])
@require_auth
def download_video(guide_id):
    """Download or redirect to the generated video."""
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404
        if not guide.video_path:
            return jsonify({"error": "No video available"}), 404

        if guide.video_path.startswith("http"):
            return redirect(guide.video_path)
        return send_file(guide.video_path, mimetype="video/mp4", as_attachment=True,
                        download_name=f"{guide.title}.mp4")
    finally:
        db.close()


@training_guide_bp.route('/<guide_id>/slides', methods=['GET'])
@require_auth
def download_slides(guide_id):
    """Download slide deck (PPTX or PDF based on format param)."""
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404

        fmt = request.args.get('format', 'pptx')
        if fmt == 'pdf' and guide.slides_pdf_path:
            path = guide.slides_pdf_path
            mime = "application/pdf"
            ext = "pdf"
        elif guide.slides_path:
            path = guide.slides_path
            mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            ext = "pptx"
        else:
            return jsonify({"error": "No slides available"}), 404

        if path.startswith("http"):
            return redirect(path)
        return send_file(path, mimetype=mime, as_attachment=True,
                        download_name=f"{guide.title}.{ext}")
    finally:
        db.close()


# ============================================================================
# UPDATE & DELETE
# ============================================================================

@training_guide_bp.route('/<guide_id>', methods=['PUT'])
@require_auth
def update_guide(guide_id):
    """Update a draft guide's outline or settings."""
    data = request.get_json() or {}
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404

        if guide.status != TrainingGuideStatus.DRAFT:
            return jsonify({"error": "Can only edit guides in draft status"}), 400

        for field in ['title', 'description', 'content_outline', 'instructions',
                      'video_style', 'video_format', 'slide_format']:
            if field in data:
                setattr(guide, field, data[field])

        if 'source_document_ids' in data:
            # Verify docs belong to tenant
            doc_ids = data['source_document_ids']
            valid = db.query(Document.id).filter(
                Document.id.in_(doc_ids),
                Document.tenant_id == g.tenant_id,
            ).all()
            guide.source_document_ids = [d.id for d in valid]

        db.commit()
        return jsonify({"guide": guide.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@training_guide_bp.route('/<guide_id>', methods=['DELETE'])
@require_auth
def delete_guide(guide_id):
    """Delete a training guide and its generated files."""
    db = get_db()
    try:
        guide = db.query(TrainingGuide).filter_by(
            id=guide_id, tenant_id=g.tenant_id
        ).first()
        if not guide:
            return jsonify({"error": "Training guide not found"}), 404

        # TODO: cleanup S3 files if needed

        db.delete(guide)
        db.commit()
        return jsonify({"message": "Training guide deleted"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# SERVICE STATUS
# ============================================================================

@training_guide_bp.route('/service-status', methods=['GET'])
@require_auth
def service_status():
    """Check if NotebookLM service is available."""
    service = get_notebooklm_service()
    return jsonify({
        "available": service.is_available,
        "video_styles": [
            "classic", "whiteboard", "kawaii", "anime",
            "watercolor", "retro_print", "heritage", "paper_craft", "auto",
        ],
        "video_formats": ["explainer", "brief"],
        "slide_formats": ["detailed_deck", "presenter_slides"],
    })
