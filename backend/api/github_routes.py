"""
GitHub Integration API Routes
OAuth flow, repository listing, and code analysis.
"""

import uuid
import json
import threading
from flask import Blueprint, request, jsonify, redirect, g
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from database.models import SessionLocal, Connector, Document, DocumentClassification, DocumentStatus, ConnectorType, ConnectorStatus, SyncMetrics, DocumentChunk, KnowledgeGap
from connectors.github_connector import GitHubConnector
from services.code_analysis_service import CodeAnalysisService
from services.code_analysis_service_v2 import CodeAnalysisServiceV2
from services.auth_service import require_auth
from services.extraction_service import ExtractionService
from services.embedding_service import EmbeddingService
from services.sync_progress_service import get_sync_progress_service
from tasks.embedding_tasks import generate_embeddings_task


github_bp = Blueprint('github', __name__, url_prefix='/api/integrations/github')


def get_db():
    """Get database session"""
    return SessionLocal()


def _run_github_sync_multi(tenant_id: str, connector_id: str, sync_id: str, repositories: list = None, max_files: int = 100, max_files_to_analyze: int = 5, notify_email: str = None):
    """
    Background worker for syncing MULTIPLE GitHub repositories.
    Syncs each repo sequentially and tracks overall progress.
    Optionally sends email notification on completion.
    """
    import time
    progress_service = get_sync_progress_service()
    db = get_db()
    sync_start_time = time.time()

    try:
        # Get connector
        connector = db.query(Connector).filter(Connector.id == connector_id).first()
        if not connector:
            progress_service.update_progress(sync_id, status='error', error_message='GitHub connector not found')
            return

        access_token = connector.access_token
        github = GitHubConnector(access_token=access_token)

        # If no repos specified, get the most recent one
        if not repositories:
            repos = github.get_repositories()
            if not repos:
                progress_service.update_progress(sync_id, status='error', error_message='No repositories found')
                return
            repos.sort(key=lambda r: r.get('updated_at', ''), reverse=True)
            repositories = [repos[0]['full_name']]

        total_repos = len(repositories)
        all_documents_created = []
        total_expected_docs = 0

        print(f"[GitHub Multi-Sync] Starting sync of {total_repos} repositories")

        # First pass: prescan all repos to get total expected documents
        repo_prescans = {}
        for repo in repositories:
            try:
                owner, repo_name = repo.split('/', 1)
                tree = github.get_repository_tree(owner, repo_name)
                code_files = github.filter_code_files(tree, max_files=1000)
                file_count = len(code_files)

                # Smart document count: small repos get all files, larger repos get key files
                if file_count <= 20:
                    expected_docs = 2 + file_count  # All files
                elif file_count <= 50:
                    expected_docs = 2 + min(30, file_count)  # Up to 30 files
                else:
                    expected_docs = 2 + min(40, file_count)  # Up to 40 key files

                repo_prescans[repo] = {'file_count': file_count, 'expected_docs': expected_docs}
                total_expected_docs += expected_docs
            except Exception as e:
                print(f"[GitHub Multi-Sync] Prescan failed for {repo}: {e}")
                repo_prescans[repo] = {'file_count': 0, 'expected_docs': 2, 'error': str(e)}
                total_expected_docs += 2

        # Update progress with total
        progress_service.update_progress(
            sync_id,
            status='syncing',
            stage=f'Syncing {total_repos} repositories...',
            total_items=total_expected_docs,
            processed_items=0,
            current_item=f'Starting sync of {total_repos} repos'
        )

        # Process each repository
        docs_processed = 0
        for repo_idx, repository in enumerate(repositories):
            repo_num = repo_idx + 1
            prescan = repo_prescans.get(repository, {})

            print(f"[GitHub Multi-Sync] Processing repo {repo_num}/{total_repos}: {repository}")

            progress_service.update_progress(
                sync_id,
                stage=f'Repo {repo_num}/{total_repos}: {repository}',
                current_item=f'Analyzing {repository}...'
            )

            try:
                # Sync this single repository
                repo_docs = _sync_single_repo(
                    db=db,
                    github=github,
                    connector=connector,
                    tenant_id=tenant_id,
                    repository=repository,
                    max_files=max_files,
                    max_files_to_analyze=max_files_to_analyze,
                    progress_service=progress_service,
                    sync_id=sync_id,
                    repo_num=repo_num,
                    total_repos=total_repos,
                    docs_processed_so_far=docs_processed,
                    total_expected_docs=total_expected_docs
                )
                all_documents_created.extend(repo_docs)
                docs_processed += len(repo_docs)

            except Exception as e:
                print(f"[GitHub Multi-Sync] Error syncing {repository}: {e}")
                import traceback
                traceback.print_exc()
                # Continue to next repo instead of failing entirely
                progress_service.update_progress(
                    sync_id,
                    current_item=f'Error syncing {repository}: {str(e)[:50]}'
                )

        # Final completion
        sync_duration = time.time() - sync_start_time
        progress_service.update_progress(
            sync_id,
            status='completed',  # Must be 'completed' (with 'd') for frontend to recognize
            stage=f'Sync complete! {len(all_documents_created)} documents from {total_repos} repos.',
            total_items=len(all_documents_created),
            processed_items=len(all_documents_created)
        )

        # Reset connector status
        connector.status = ConnectorStatus.CONNECTED
        connector.last_sync_at = datetime.now(timezone.utc)
        connector.settings = {**(connector.settings or {}), 'current_sync_id': None, 'sync_progress': None}
        db.commit()

        print(f"[GitHub Multi-Sync] Complete: {len(all_documents_created)} documents from {total_repos} repos")

        # Send email notification if requested
        if notify_email:
            try:
                from services.email_notification_service import get_email_service
                email_service = get_email_service()
                email_service.send_sync_complete_notification(
                    user_email=notify_email,
                    connector_type='github',
                    total_items=len(all_documents_created),
                    processed_items=len(all_documents_created),
                    failed_items=0,
                    duration_seconds=sync_duration
                )
                print(f"[GitHub Multi-Sync] Email notification sent to {notify_email}")
            except Exception as e:
                print(f"[GitHub Multi-Sync] Failed to send email notification: {e}")

    except Exception as e:
        print(f"[GitHub Multi-Sync] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        progress_service.update_progress(sync_id, status='error', error_message=str(e))

        # Reset connector status on error
        try:
            connector = db.query(Connector).filter(Connector.id == connector_id).first()
            if connector:
                connector.status = ConnectorStatus.CONNECTED
                connector.settings = {**(connector.settings or {}), 'current_sync_id': None}
                db.commit()
        except:
            pass

    finally:
        db.close()


def _sync_single_repo(db, github, connector, tenant_id: str, repository: str, max_files: int,
                      max_files_to_analyze: int, progress_service, sync_id: str,
                      repo_num: int, total_repos: int, docs_processed_so_far: int, total_expected_docs: int):
    """
    Sync a single repository using V2 tree-sitter pipeline.
    Creates per-function/class documents + diagram documents.
    """
    import time

    if not repository or '/' not in repository:
        raise ValueError(f"Invalid repository format: {repository}")

    owner, repo_name = repository.split('/', 1)

    # Fetch repository code — fetch ALL files (no cap for V2)
    progress_service.update_progress(
        sync_id,
        stage=f'Repo {repo_num}/{total_repos}: Fetching {repository}...',
        current_item=f'Fetching all code files...'
    )

    code_files = github.fetch_repository_code(owner=owner, repo=repo_name, max_files=max(max_files, 500))
    if not code_files:
        print(f"[GitHub Sync V2] No code files in {repository}")
        return []

    file_count = len(code_files)
    print(f"[GitHub Sync V2] Fetched {file_count} code files from {repository}")

    # Update progress - tree-sitter parsing + AI analysis
    progress_service.update_progress(
        sync_id,
        stage=f'Repo {repo_num}/{total_repos}: Parsing & analyzing {file_count} files...',
        current_item=f'tree-sitter parsing + AI analysis on {repository}...'
    )

    # Get repo description
    repos = github.get_repositories()
    repo_info = next((r for r in repos if r['full_name'].lower() == repository.lower()), None)
    repo_description = repo_info['description'] if repo_info else None

    # V2 Analysis: tree-sitter + function-level LLM + diagrams
    try:
        analyzer = CodeAnalysisServiceV2()
        analysis = analyzer.analyze_repository(
            repo_name=repository,
            repo_description=repo_description,
            code_files=code_files,
        )
    except Exception as e:
        print(f"[GitHub Sync V2] V2 analysis failed: {e}, falling back to V1")
        import traceback
        traceback.print_exc()
        analyzer_v1 = CodeAnalysisService()
        analysis = analyzer_v1.analyze_repository(
            repo_name=repository,
            repo_description=repo_description,
            code_files=code_files,
            max_files_to_analyze=max_files_to_analyze
        )

    # Delete existing documents for this repository to prevent duplicates
    repo_prefix = f"github_{repository.replace('/', '_')}"
    existing_docs = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.external_id.like(f"{repo_prefix}%")
    ).all()
    if existing_docs:
        print(f"[GitHub Sync V2] Deleting {len(existing_docs)} existing documents for {repository}")
        for doc in existing_docs:
            db.delete(doc)
        db.commit()

    # Create documents
    progress_service.update_progress(
        sync_id,
        stage=f'Repo {repo_num}/{total_repos}: Creating documents...',
        current_item=f'Creating documents for {repository}...'
    )

    documents_created = []

    # 1. Main documentation document (includes diagrams in markdown)
    doc_main = Document(
        tenant_id=tenant_id,
        connector_id=connector.id,
        title=f"{repository} - Technical Documentation",
        content=analysis['documentation'],
        source_type='github',
        source_url=f"https://github.com/{repository}",
        sender_email=connector.settings.get('github_user'),
        external_id=f"github_{repository.replace('/', '_')}_docs",
        doc_metadata={'repository': repository, 'analysis_type': 'comprehensive_documentation', 'stats': analysis['stats']},
        status=DocumentStatus.CLASSIFIED,
        classification=DocumentClassification.WORK,
        classification_confidence=1.0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(doc_main)
    documents_created.append(doc_main)

    # 2. Repository overview document
    overview = analysis.get('repository_overview', {})
    tech_stack = overview.get('tech_stack', [])
    if isinstance(tech_stack, dict):
        tech_stack = list(tech_stack.keys())
    patterns = overview.get('patterns', [])
    if isinstance(patterns, dict):
        patterns = list(patterns.keys())

    overview_content = f"""# {repository} - Repository Overview

## Purpose
{overview.get('purpose', 'N/A')}

## Architecture
{overview.get('architecture', 'N/A')}

## Technology Stack
{chr(10).join(f'- {tech}' for tech in tech_stack)}

## Design Patterns
{chr(10).join(f'- {p}' for p in patterns)}

## Statistics
- Total Files: {analysis['stats']['total_files']}
- Analyzed Files: {analysis['stats']['analyzed_files']}
- Code Units Explained: {analysis['stats'].get('explained_units', 'N/A')}
- Total Lines: {analysis['stats']['total_lines']:,}
- Diagrams Generated: {analysis['stats'].get('diagrams_generated', 0)}
"""

    doc_overview = Document(
        tenant_id=tenant_id,
        connector_id=connector.id,
        title=f"{repository} - Overview",
        content=overview_content,
        source_type='github',
        source_url=f"https://github.com/{repository}",
        sender_email=connector.settings.get('github_user'),
        external_id=f"github_{repository.replace('/', '_')}_overview",
        doc_metadata={'repository': repository, 'analysis_type': 'overview'},
        status=DocumentStatus.CLASSIFIED,
        classification=DocumentClassification.WORK,
        classification_confidence=1.0,
        created_at=datetime.now(timezone.utc)
    )
    db.add(doc_overview)
    documents_created.append(doc_overview)

    # 3. Per-function/class documents (V2: the key improvement)
    code_units = analysis.get('code_units', [])
    if code_units:
        print(f"[GitHub Sync V2] Creating {len(code_units)} code unit documents")
        for unit in code_units:
            # Content: explanation + code (explanation first for better embedding)
            unit_content = f"""# {unit['name']}

**Type:** {unit['unit_type']} | **File:** {unit['file_path']} | **Lines:** {unit['line_start']}-{unit['line_end']}

## Explanation
{unit['explanation']}

## Key Details
{chr(10).join(f'- {d}' for d in unit.get('key_details', []))}

## Source Code ({unit.get('language', '')})

```{unit.get('language', '')}
{unit['code'][:15000]}
```
"""
            safe_name = unit['name'].replace('/', '_').replace('.', '_').replace('<', '').replace('>', '')
            safe_file = unit['file_path'].replace('/', '_')
            external_id = f"github_{repository.replace('/', '_')}_unit_{safe_file}_{safe_name}"

            # Build GitHub URL with line numbers
            github_file_url = f"https://github.com/{repository}/blob/main/{unit['file_path']}#L{unit['line_start']}-L{unit['line_end']}"

            doc_unit = Document(
                tenant_id=tenant_id,
                connector_id=connector.id,
                title=f"{repository} - {unit['file_path']}:{unit['name']}",
                content=unit_content,
                source_type='github',
                source_url=github_file_url,
                sender_email=connector.settings.get('github_user'),
                external_id=external_id[:500],  # Safety cap on external_id length
                doc_metadata={
                    'repository': repository,
                    'file_path': unit['file_path'],
                    'unit_type': unit['unit_type'],
                    'unit_name': unit['name'],
                    'line_start': unit['line_start'],
                    'line_end': unit['line_end'],
                    'language': unit.get('language', ''),
                    'analysis_type': 'code_unit',
                },
                status=DocumentStatus.CLASSIFIED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(doc_unit)
            documents_created.append(doc_unit)
    else:
        # V1 fallback: file-level analyses
        for file_analysis in analysis.get('file_analyses', [])[:40]:
            file_content = f"""# {file_analysis.get('file_path', 'Unknown file')}

## Summary
{file_analysis.get('summary', 'No summary available')}

## Key Functions/Classes
{chr(10).join(f'- {func}' for func in file_analysis.get('key_functions', []))}

## Dependencies
{chr(10).join(f'- {dep}' for dep in file_analysis.get('dependencies', []))}

## Business Logic
{file_analysis.get('business_logic', 'No business logic described')}
"""
            doc_file = Document(
                tenant_id=tenant_id,
                connector_id=connector.id,
                title=f"{repository} - {file_analysis['file_path']}",
                content=file_content,
                source_type='github',
                sender_email=connector.settings.get('github_user'),
                external_id=f"github_{repository.replace('/', '_')}_{file_analysis['file_path'].replace('/', '_')}",
                doc_metadata={'repository': repository, 'file_path': file_analysis['file_path'], 'analysis_type': 'file_analysis'},
                status=DocumentStatus.CLASSIFIED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(doc_file)
            documents_created.append(doc_file)

    # 4. Diagram documents (NEW: searchable and retrievable by chatbot)
    diagrams = analysis.get('diagrams', [])
    if diagrams:
        print(f"[GitHub Sync V2] Creating {len(diagrams)} diagram documents")
        for idx, diagram in enumerate(diagrams):
            diagram_content = f"""# {diagram['title']}

## Description
{diagram['description']}

## Diagram

```mermaid
{diagram['mermaid']}
```
"""
            safe_type = diagram.get('diagram_type', 'diagram')
            doc_diagram = Document(
                tenant_id=tenant_id,
                connector_id=connector.id,
                title=diagram['title'],
                content=diagram_content,
                source_type='github',
                source_url=f"https://github.com/{repository}",
                sender_email=connector.settings.get('github_user'),
                external_id=f"github_{repository.replace('/', '_')}_diagram_{safe_type}_{idx}",
                doc_metadata={
                    'repository': repository,
                    'analysis_type': 'diagram',
                    'diagram_type': safe_type,
                },
                status=DocumentStatus.CLASSIFIED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(doc_diagram)
            documents_created.append(doc_diagram)

    # 5. Flow documents (NEW: cross-file walkthroughs that match conversational queries)
    flows = analysis.get('flows', [])
    if flows:
        print(f"[GitHub Sync V2] Creating {len(flows)} flow documents")
        for idx, flow in enumerate(flows):
            steps_text = '\n'.join(flow.get('steps', []))
            files_text = ', '.join(flow.get('files_involved', []))
            concepts_text = ', '.join(flow.get('key_concepts', []))

            flow_content = f"""# {flow['title']}

## Description
{flow.get('description', '')}

## Step-by-Step Walkthrough
{steps_text}

## Files Involved
{files_text}

## Key Concepts
{concepts_text}
"""
            doc_flow = Document(
                tenant_id=tenant_id,
                connector_id=connector.id,
                title=f"{repository} - Flow: {flow['title'][:80]}",
                content=flow_content,
                source_type='github',
                source_url=f"https://github.com/{repository}",
                sender_email=connector.settings.get('github_user'),
                external_id=f"github_{repository.replace('/', '_')}_flow_{idx}",
                doc_metadata={
                    'repository': repository,
                    'analysis_type': 'flow',
                    'files_involved': flow.get('files_involved', []),
                },
                status=DocumentStatus.CLASSIFIED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(doc_flow)
            documents_created.append(doc_flow)

    db.commit()
    print(f"[GitHub Sync V2] Created {len(documents_created)} documents for {repository}")

    # Extract structured summaries and embed
    extraction_service = ExtractionService()
    embedding_service = EmbeddingService()

    for i, doc in enumerate(documents_created):
        db.refresh(doc)

        # Extract
        try:
            extraction_service.extract_document(doc, db)
        except Exception as e:
            print(f"[GitHub Sync V2] Extraction failed for {doc.title}: {e}")

        # Embed - pass Document object, not ID
        try:
            embedding_service.embed_documents([doc], tenant_id, db)
        except Exception as e:
            print(f"[GitHub Sync V2] Embedding failed for {doc.title}: {e}")

        # Update progress
        current_processed = docs_processed_so_far + i + 1
        progress_service.update_progress(
            sync_id,
            total_items=max(total_expected_docs, len(documents_created)),
            processed_items=current_processed,
            current_item=f'{repository}: {doc.title[:40]}...'
        )

    return documents_created


def _run_github_sync(tenant_id: str, connector_id: str, sync_id: str, repository: str = None, max_files: int = 100, max_files_to_analyze: int = 5):
    """
    Background worker for GitHub sync.
    Updates progress via SSE and does the actual sync work.
    """
    import time
    progress_service = get_sync_progress_service()
    db = get_db()
    sync_start_time = time.time()  # Track for adaptive estimation

    try:
        print(f"[GitHub Sync] Starting background sync for tenant {tenant_id}, sync_id {sync_id}")

        # Update progress - connecting
        progress_service.update_progress(
            sync_id,
            status='connecting',
            stage='Connecting to GitHub...'
        )

        # Get connector from DB
        connector = db.query(Connector).filter(
            Connector.id == connector_id
        ).first()

        if not connector:
            progress_service.update_progress(
                sync_id,
                status='error',
                error_message='GitHub connector not found'
            )
            return

        access_token = connector.access_token
        github = GitHubConnector(access_token=access_token)

        # Store sync_id in connector settings for multi-worker SSE fallback
        connector.settings = {
            **(connector.settings or {}),
            'current_sync_id': sync_id,
            'sync_progress': {
                'status': 'connecting',
                'stage': 'Connecting to GitHub...',
                'total_items': 0,
                'processed_items': 0,
                'failed_items': 0
            }
        }
        db.commit()

        # Update progress - fetching repos
        progress_service.update_progress(
            sync_id,
            status='syncing',
            stage='Fetching repository list...'
        )

        # Get repository to sync
        if not repository:
            print("[GitHub Sync] No repository specified, fetching most recent repo")
            repos = github.get_repositories()
            if not repos:
                progress_service.update_progress(
                    sync_id,
                    status='error',
                    error_message='No repositories found. Please create a repository on GitHub first.'
                )
                return

            repos.sort(key=lambda r: r.get('updated_at', ''), reverse=True)
            repository = repos[0]['full_name']
            print(f"[GitHub Sync] Auto-selected most recent repository: {repository}")

        if not repository or '/' not in repository:
            progress_service.update_progress(
                sync_id,
                status='error',
                error_message=f"Invalid repository format: {repository}. Use 'owner/repo'"
            )
            return

        owner, repo = repository.split('/', 1)

        # PRE-SCAN: Count files first so user knows what to expect
        progress_service.update_progress(
            sync_id,
            status='syncing',
            stage=f'Scanning {repository}...',
            current_item=repository
        )

        # Quick scan to get file count
        print(f"[GitHub Sync] Pre-scanning repository tree: {repository}")
        tree = github.get_repository_tree(owner, repo)
        code_files_preview = github.filter_code_files(tree, max_files=1000)
        file_count = len(code_files_preview)

        # Calculate expected documents (matches prescan logic)
        files_to_process = min(file_count, max_files)
        expected_documents = min(12, 2 + min(10, files_to_process))

        # Realistic time estimation (matches prescan)
        adaptive_rate = SyncMetrics.get_average_rate(db, tenant_id, ConnectorType.GITHUB)
        llm_analysis_time = 60  # LLM is the bottleneck
        fetch_time = files_to_process * 0.1
        doc_processing_time = expected_documents * (adaptive_rate + 3 + 2)
        estimated_seconds = int(llm_analysis_time + fetch_time + doc_processing_time)

        if estimated_seconds < 60:
            time_estimate = f"~{estimated_seconds} seconds"
        elif estimated_seconds < 120:
            time_estimate = "~1-2 minutes"
        elif estimated_seconds < 180:
            time_estimate = "~2-3 minutes"
        else:
            time_estimate = f"~{estimated_seconds // 60} minutes"

        print(f"[GitHub Sync] Found {file_count} files, will create {expected_documents} docs, est: {time_estimate}")

        # Helper to update both in-memory and database progress (for multi-worker SSE fallback)
        def update_db_progress(status, stage, total=None, processed=None, current=None):
            connector.settings = {
                **(connector.settings or {}),
                'current_sync_id': sync_id,
                'sync_progress': {
                    'status': status,
                    'stage': stage,
                    'total_items': total if total is not None else (connector.settings or {}).get('sync_progress', {}).get('total_items', 0),
                    'processed_items': processed if processed is not None else (connector.settings or {}).get('sync_progress', {}).get('processed_items', 0),
                    'failed_items': 0,
                    'current_item': current
                }
            }
            try:
                db.commit()
            except Exception:
                db.rollback()

        # Report count immediately so user sees expected document count
        progress_service.update_progress(
            sync_id,
            status='syncing',
            stage=f'Fetching {file_count} files ({time_estimate})',
            total_items=expected_documents,
            processed_items=0,
            current_item=f'Fetching from {repository}...'
        )
        update_db_progress('syncing', f'Fetching {file_count} files ({time_estimate})', total=expected_documents, processed=0, current=f'Fetching from {repository}...')

        # Fetch repository code
        print(f"[GitHub Sync] Fetching code from {repository}")
        code_files = github.fetch_repository_code(
            owner=owner,
            repo=repo,
            max_files=max_files
        )

        if not code_files:
            progress_service.update_progress(
                sync_id,
                status='error',
                error_message='No code files found in repository'
            )
            return

        print(f"[GitHub Sync] Fetched {len(code_files)} code files")

        # Update progress - analyzing with AI (this is the longest phase)
        progress_service.update_progress(
            sync_id,
            status='syncing',
            stage=f'AI analyzing {len(code_files)} files (this takes ~1 min)...',
            total_items=expected_documents,
            processed_items=0,
            current_item='Running AI analysis...'
        )
        update_db_progress('syncing', f'AI analyzing {len(code_files)} files...', total=expected_documents, processed=0, current='Running AI analysis...')

        # Get repository info for description
        repos = github.get_repositories()
        repo_info = next(
            (r for r in repos if r['full_name'].lower() == repository.lower()),
            None
        )
        repo_description = repo_info['description'] if repo_info else None

        # Analyze repository with V2 (tree-sitter + function-level LLM)
        print(f"[GitHub Sync] Analyzing repository with V2 pipeline")
        try:
            analyzer = CodeAnalysisServiceV2()
            analysis = analyzer.analyze_repository(
                repo_name=repository,
                repo_description=repo_description,
                code_files=code_files,
            )
        except Exception as e:
            print(f"[GitHub Sync] V2 analysis failed: {e}, falling back to V1")
            try:
                analyzer_v1 = CodeAnalysisService()
                analysis = analyzer_v1.analyze_repository(
                    repo_name=repository,
                    repo_description=repo_description,
                    code_files=code_files,
                    max_files_to_analyze=max_files_to_analyze
                )
            except Exception as e2:
                print(f"[GitHub Sync] V1 also failed: {e2}")
                progress_service.update_progress(
                    sync_id,
                    status='error',
                    error_message=f'AI analysis failed: {str(e2)}'
                )
                return

        # Update progress - AI done, creating documents
        progress_service.update_progress(
            sync_id,
            status='parsing',
            stage='Creating documents from analysis...',
            total_items=expected_documents,
            processed_items=0,
            current_item='AI analysis complete'
        )
        update_db_progress('parsing', 'Creating documents from analysis...', total=expected_documents, processed=0, current='AI analysis complete')

        # Delete existing documents for this repository to prevent duplicates
        repo_prefix = f"github_{repository.replace('/', '_')}"
        existing_docs = db.query(Document).filter(
            Document.tenant_id == tenant_id,
            Document.external_id.like(f"{repo_prefix}%")
        ).all()

        if existing_docs:
            print(f"[GitHub Sync] Deleting {len(existing_docs)} existing documents for {repository}")
            for doc in existing_docs:
                db.delete(doc)
            db.commit()

        # Store as documents
        documents_created = []

        # 1. Main documentation document
        doc_main = Document(
            tenant_id=tenant_id,
            connector_id=connector_id,
            title=f"{repository} - Technical Documentation",
            content=analysis['documentation'],
            source_type='github',
            sender_email=connector.settings.get('github_user'),
            external_id=f"github_{repository.replace('/', '_')}_docs",
            doc_metadata={
                'repository': repository,
                'analysis_type': 'comprehensive_documentation',
                'stats': analysis['stats']
            },
            status=DocumentStatus.CLASSIFIED,
            classification=DocumentClassification.WORK,
            classification_confidence=1.0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(doc_main)
        documents_created.append(doc_main)

        # 2. Repository overview document
        overview_content = f"""# {repository} - Repository Overview

## Purpose
{analysis['repository_overview']['purpose']}

## Architecture
{analysis['repository_overview']['architecture']}

## Technology Stack
{chr(10).join(f'- {tech}' for tech in analysis['repository_overview']['tech_stack'])}

## Design Patterns
{chr(10).join(f'- {pattern}' for pattern in analysis['repository_overview']['patterns'])}

## Components
{json.dumps(analysis['repository_overview']['components'], indent=2)}

## Statistics
- Total Files: {analysis['stats']['total_files']}
- Analyzed Files: {analysis['stats']['analyzed_files']}
- Total Lines: {analysis['stats']['total_lines']:,}
- Languages: {', '.join(f"{k} ({v})" for k, v in analysis['stats']['languages'].items())}
"""

        doc_overview = Document(
            tenant_id=tenant_id,
            connector_id=connector_id,
            title=f"{repository} - Overview",
            content=overview_content,
            source_type='github',
            sender_email=connector.settings.get('github_user'),
            external_id=f"github_{repository.replace('/', '_')}_overview",
            doc_metadata={
                'repository': repository,
                'analysis_type': 'overview',
                'overview': analysis['repository_overview']
            },
            status=DocumentStatus.CLASSIFIED,
            classification=DocumentClassification.WORK,
            classification_confidence=1.0,
            created_at=datetime.now(timezone.utc)
        )
        db.add(doc_overview)
        documents_created.append(doc_overview)

        # 3. Individual file analyses (top 10)
        for file_analysis in analysis['file_analyses'][:10]:
            file_content = f"""# {file_analysis.get('file_path', 'Unknown file')}

## Summary
{file_analysis.get('summary', 'No summary available')}

## Language
{file_analysis.get('language', 'Unknown')}

## Key Functions/Classes
{chr(10).join(f'- {func}' for func in file_analysis.get('key_functions', []))}

## Dependencies
{chr(10).join(f'- {dep}' for dep in file_analysis.get('dependencies', []))}

## Business Logic
{file_analysis.get('business_logic', 'No business logic described')}

## API Endpoints
{chr(10).join(f'- {ep}' for ep in file_analysis.get('api_endpoints', []))}

## Data Models
{chr(10).join(f'- {model}' for model in file_analysis.get('data_models', []))}

## Important Notes
{chr(10).join(f'- {note}' for note in file_analysis.get('important_notes', []))}
"""

            doc_file = Document(
                tenant_id=tenant_id,
                connector_id=connector_id,
                title=f"{repository} - {file_analysis['file_path']}",
                content=file_content,
                source_type='github',
                sender_email=connector.settings.get('github_user'),
                external_id=f"github_{repository.replace('/', '_')}_{file_analysis['file_path'].replace('/', '_')}",
                doc_metadata={
                    'repository': repository,
                    'file_path': file_analysis['file_path'],
                    'analysis_type': 'file_analysis',
                    'language': file_analysis['language']
                },
                status=DocumentStatus.CLASSIFIED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                created_at=datetime.now(timezone.utc)
            )
            db.add(doc_file)
            documents_created.append(doc_file)

        # Commit documents
        db.commit()
        print(f"[GitHub Sync] Created {len(documents_created)} documents")

        # Update progress - extracting summaries
        progress_service.update_progress(
            sync_id,
            status='parsing',
            stage=f'Extracting summaries from {len(documents_created)} documents...',
            total_items=len(documents_created),
            processed_items=0,
            current_item=f'Created {len(documents_created)} documents'
        )
        update_db_progress('parsing', f'Extracting summaries...', total=len(documents_created), processed=0, current=f'Created {len(documents_created)} docs')

        # Extract structured summaries
        extraction_service = ExtractionService()
        for i, doc in enumerate(documents_created):
            db.refresh(doc)
            try:
                extraction_service.extract_document(doc, db)
            except Exception as e:
                print(f"[GitHub Sync] Extraction failed for {doc.title}: {e}")

            progress_service.update_progress(
                sync_id,
                total_items=len(documents_created),
                processed_items=i + 1,
                current_item=doc.title[:50]
            )

        # Update progress - embedding
        progress_service.update_progress(
            sync_id,
            status='embedding',
            stage=f'Creating embeddings for {len(documents_created)} documents...',
            total_items=len(documents_created),
            processed_items=0,
            current_item='Starting embeddings...'
        )
        update_db_progress('embedding', 'Creating embeddings...', total=len(documents_created), processed=0, current='Embedding documents')

        # Embed documents - pass Document objects, not IDs
        print(f"[GitHub Sync] Embedding {len(documents_created)} documents...")
        embedding_service = EmbeddingService()

        for i, doc in enumerate(documents_created):
            try:
                embedding_service.embed_documents([doc], tenant_id, db)
            except Exception as e:
                print(f"[GitHub Sync] Embedding failed for doc {doc.id}: {e}")

            progress_service.update_progress(
                sync_id,
                total_items=len(documents_created),
                processed_items=i + 1,
                current_item=f'Embedding {i + 1}/{len(documents_created)}'
            )

        print(f"[GitHub Sync] Embedded {len(documents_created)} documents successfully")

        # Update connector last_sync_at
        connector.last_sync_at = datetime.now(timezone.utc)
        db.commit()

        # Record actual sync time for adaptive estimation (non-critical - don't fail sync if this fails)
        actual_duration = time.time() - sync_start_time
        if file_count > 0:
            try:
                seconds_per_file = actual_duration / file_count
                sync_metric = SyncMetrics(
                    tenant_id=tenant_id,
                    connector_type=ConnectorType.GITHUB,
                    file_count=file_count,
                    actual_duration_seconds=actual_duration,
                    seconds_per_file=seconds_per_file,
                    repository=repository,
                    sync_id=sync_id
                )
                db.add(sync_metric)
                db.commit()
                print(f"[GitHub Sync] Recorded metrics: {file_count} files in {actual_duration:.1f}s ({seconds_per_file:.2f}s/file)")
            except Exception as metric_err:
                # Don't fail the sync just because metrics recording failed (table might not exist)
                print(f"[GitHub Sync] Warning: Could not record sync metrics: {metric_err}")
                db.rollback()  # Rollback the failed metric insert

        # Mark complete
        progress_service.update_progress(
            sync_id,
            status='completed',  # Must be 'completed' (with 'd') for frontend to recognize
            stage=f'Sync complete! Created {len(documents_created)} documents.',
            total_items=len(documents_created),
            processed_items=len(documents_created)
        )
        update_db_progress('completed', f'Sync complete! {len(documents_created)} documents.', total=len(documents_created), processed=len(documents_created))

        # Clear current_sync_id and reset connector status now that sync is done
        connector.status = ConnectorStatus.CONNECTED  # Reset from SYNCING
        connector.settings = {
            **(connector.settings or {}),
            'current_sync_id': None,
            'sync_progress': None
        }
        try:
            db.commit()
            print(f"[GitHub Sync] Reset connector status to CONNECTED")
        except Exception as e:
            print(f"[GitHub Sync] Warning: Could not reset connector status: {e}")

        print(f"[GitHub Sync] Sync complete: {len(documents_created)} documents")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[GitHub Sync] Error: {e}")
        progress_service.update_progress(
            sync_id,
            status='error',
            error_message=str(e)
        )
        # Also save error to DB for multi-worker SSE fallback
        try:
            connector = db.query(Connector).filter(Connector.id == connector_id).first()
            if connector:
                connector.settings = {
                    **(connector.settings or {}),
                    'current_sync_id': sync_id,
                    'sync_progress': {
                        'status': 'error',
                        'stage': 'Sync failed',
                        'error_message': str(e),
                        'total_items': 0,
                        'processed_items': 0,
                        'failed_items': 0
                    }
                }
                connector.status = ConnectorStatus.CONNECTED  # Reset status
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ============================================================================
# OAUTH FLOW
# NOTE: /auth and /callback routes are in integration_routes.py
# This avoids duplicate route registration conflicts.
# ============================================================================


@github_bp.route('/connect', methods=['POST'])
@require_auth
def connect_github():
    """
    Save GitHub connection after OAuth.

    Request body:
    {
        "access_token": "gho_...",
        "refresh_token": "optional"
    }

    Response:
    {
        "success": true,
        "connector": {...}
    }
    """
    try:
        data = request.get_json()
        access_token = data.get('access_token')

        if not access_token:
            return jsonify({
                "success": False,
                "error": "Access token is required"
            }), 400

        # Get user info from GitHub
        connector = GitHubConnector(access_token=access_token)
        user_info = connector.get_user_info()

        # Check rate limit
        rate_limit = connector.get_rate_limit()

        db = get_db()
        try:
            # Check if connector already exists
            existing = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.GITHUB
            ).first()

            if existing:
                # Update existing connector
                existing.access_token = access_token
                existing.refresh_token = data.get('refresh_token')
                existing.settings = {
                    'github_user': user_info['login'],
                    'github_user_id': user_info['id']
                }
                existing.status = ConnectorStatus.CONNECTED
                existing.last_sync_at = None
                existing.updated_at = datetime.now(timezone.utc)

                db.commit()
                db.refresh(existing)

                return jsonify({
                    "success": True,
                    "connector": existing.to_dict(),
                    "github_user": user_info['login'],
                    "rate_limit": rate_limit
                })

            # Create new connector
            new_connector = Connector(
                tenant_id=g.tenant_id,
                connector_type=ConnectorType.GITHUB,
                access_token=access_token,
                refresh_token=data.get('refresh_token'),
                settings={
                    'github_user': user_info['login'],
                    'github_user_id': user_info['id']
                },
                status=ConnectorStatus.CONNECTED,
                created_at=datetime.now(timezone.utc)
            )

            db.add(new_connector)
            db.commit()
            db.refresh(new_connector)

            return jsonify({
                "success": True,
                "connector": new_connector.to_dict(),
                "github_user": user_info['login'],
                "rate_limit": rate_limit
            }), 201

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# REPOSITORY LISTING
# ============================================================================

@github_bp.route('/repositories', methods=['GET'])
@require_auth
def list_repositories():
    """
    List GitHub repositories accessible to user.
    Supports pagination for lazy loading.

    Query params:
        page: Page number (default 1)
        per_page: Results per page (default 10, max 100)

    Response:
    {
        "success": true,
        "repositories": [...],
        "count": 10,
        "page": 1,
        "per_page": 10,
        "has_more": true
    }
    """
    try:
        # Get pagination params
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)

        db = get_db()
        try:
            # Accept both CONNECTED and SYNCING (in case previous sync didn't reset status)
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.GITHUB,
                Connector.status.in_([ConnectorStatus.CONNECTED, ConnectorStatus.SYNCING])
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "GitHub not connected"
                }), 404

            # Reset stuck SYNCING status
            if connector.status == ConnectorStatus.SYNCING:
                connector.status = ConnectorStatus.CONNECTED
                db.commit()

            access_token = connector.access_token
            github = GitHubConnector(access_token=access_token)

            # Fetch single page from GitHub API directly (fast!)
            import requests
            response = requests.get(
                'https://api.github.com/user/repos',
                headers={
                    'Authorization': f'Bearer {access_token}',
                    'Accept': 'application/vnd.github+json',
                    'X-GitHub-Api-Version': '2022-11-28'
                },
                params={
                    'per_page': per_page,
                    'page': page,
                    'sort': 'updated',
                    'affiliation': 'owner,collaborator,organization_member'
                }
            )
            response.raise_for_status()
            repositories = response.json()

            # Check if there are more pages by checking if we got a full page
            has_more = len(repositories) == per_page

            return jsonify({
                "success": True,
                "repositories": repositories,
                "count": len(repositories),
                "page": page,
                "per_page": per_page,
                "has_more": has_more
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# PRE-SCAN REPOSITORY (count files before sync)
# ============================================================================

@github_bp.route('/prescan', methods=['POST'])
@require_auth
def prescan_repository():
    """
    Pre-scan a GitHub repository to count files before syncing.
    This helps users understand sync scope and estimated time.

    Request body:
    {
        "repository": "owner/repo"  # optional - if not provided, uses most recent repo
    }

    Response:
    {
        "success": true,
        "repository": "owner/repo",
        "file_count": 150,
        "estimated_time_seconds": 45,
        "estimated_time_display": "~1 minute"
    }
    """
    try:
        data = request.get_json() or {}
        repository = data.get('repository')

        db = get_db()
        try:
            # Get GitHub connector (accept SYNCING too in case previous sync didn't reset)
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.GITHUB,
                Connector.status.in_([ConnectorStatus.CONNECTED, ConnectorStatus.SYNCING])
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "GitHub not connected"
                }), 404

            # Reset stuck SYNCING status
            if connector.status == ConnectorStatus.SYNCING:
                connector.status = ConnectorStatus.CONNECTED
                db.commit()

            access_token = connector.access_token
            github = GitHubConnector(access_token=access_token)

            # Get repository to scan
            if not repository:
                repos = github.get_repositories()
                if not repos:
                    return jsonify({
                        "success": False,
                        "error": "No repositories found"
                    }), 404
                repos.sort(key=lambda r: r.get('updated_at', ''), reverse=True)
                repository = repos[0]['full_name']

            if not repository or '/' not in repository:
                return jsonify({
                    "success": False,
                    "error": f"Invalid repository format: {repository}"
                }), 400

            owner, repo = repository.split('/', 1)

            # Get repository tree
            tree = github.get_repository_tree(owner, repo)

            # Filter to code files
            code_files = github.filter_code_files(tree, max_files=1000)
            file_count = len(code_files)

            # Smart document count based on repo size:
            # - Small repos (≤20 files): Document all files
            # - Medium repos (21-50 files): Up to 30 key files
            # - Large repos (50+ files): Up to 40 key files
            files_to_process = min(file_count, 100)
            if file_count <= 20:
                expected_documents = 2 + file_count  # 2 summaries + all files
            elif file_count <= 50:
                expected_documents = 2 + min(30, file_count)  # 2 summaries + up to 30 files
            else:
                expected_documents = 2 + min(40, file_count)  # 2 summaries + up to 40 key files

            # Adaptive time estimation based on historical sync data
            adaptive_rate = SyncMetrics.get_average_rate(db, g.tenant_id, ConnectorType.GITHUB)

            # Time breakdown:
            # - Fetch files: ~0.1s per file
            # - LLM analysis: ~60s base + more for larger repos
            # - Create documents: ~1s
            # - Extract summaries: ~3s per doc
            # - Embed documents: ~2s per doc
            llm_analysis_time = 60 + (files_to_process // 20) * 15  # Base + extra for larger repos
            fetch_time = files_to_process * 0.1
            doc_processing_time = expected_documents * (adaptive_rate + 3 + 2)  # rate + extraction + embedding

            estimated_seconds = llm_analysis_time + fetch_time + doc_processing_time

            print(f"[Prescan] {repository}: {file_count} files, {expected_documents} docs, est: {estimated_seconds:.0f}s")

            # Format display time
            if estimated_seconds < 60:
                time_display = f"~{int(estimated_seconds)} seconds"
            elif estimated_seconds < 120:
                time_display = "~1-2 minutes"
            elif estimated_seconds < 180:
                time_display = "~2-3 minutes"
            elif estimated_seconds < 300:
                time_display = "~3-5 minutes"
            else:
                time_display = f"~{int(estimated_seconds / 60)} minutes"

            return jsonify({
                "success": True,
                "repository": repository,
                "file_count": file_count,
                "expected_documents": expected_documents,
                "estimated_time_seconds": int(estimated_seconds),
                "estimated_time_display": time_display
            })

        finally:
            db.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SYNC & ANALYZE REPOSITORY
# ============================================================================

@github_bp.route('/sync', methods=['POST'])
@require_auth
def sync_repository():
    """
    Sync and analyze GitHub repositories.
    Returns immediately with sync_id - actual work happens in background.
    Supports syncing multiple repositories in one request.

    Request body (all optional):
    {
        "repository": "user/repo",  # single repo (legacy)
        "repositories": ["user/repo1", "user/repo2"],  # multiple repos (preferred)
        "max_files": 100,  # optional
        "max_files_to_analyze": 5  # optional (default 5 to prevent timeouts)
    }

    Response:
    {
        "success": true,
        "sync_id": "uuid",
        "message": "GitHub sync started in background",
        "repositories": ["user/repo1", "user/repo2"]
    }
    """
    try:
        data = request.get_json() or {}
        # Support both single repository and multiple repositories
        repositories = data.get('repositories', [])
        if not repositories and data.get('repository'):
            repositories = [data.get('repository')]
        max_files = data.get('max_files', 100)
        max_files_to_analyze = data.get('max_files_to_analyze', 5)
        notify_email = data.get('notify_email')  # Email to notify on completion

        db = get_db()
        try:
            # Get GitHub connector (accept SYNCING too in case previous sync didn't reset)
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.GITHUB,
                Connector.status.in_([ConnectorStatus.CONNECTED, ConnectorStatus.SYNCING])
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "GitHub not connected"
                }), 404

            # Reset status to CONNECTED first (will be set to SYNCING below)
            if connector.status == ConnectorStatus.SYNCING:
                connector.status = ConnectorStatus.CONNECTED
                db.commit()

            connector_id = connector.id
            tenant_id = g.tenant_id
            user_id = g.user_id

            # Initialize progress - start_sync returns the sync_id
            progress_service = get_sync_progress_service()
            sync_id = progress_service.start_sync(
                tenant_id=tenant_id,
                user_id=user_id,
                connector_type='github'
            )

            # Save sync_id to connector BEFORE starting thread (for multi-worker SSE fallback)
            repo_count = len(repositories) if repositories else 1
            print(f"[GitHub] Saving sync_id {sync_id} to connector {connector_id} settings...")
            connector.settings = {
                **(connector.settings or {}),
                'current_sync_id': sync_id,
                'sync_progress': {
                    'status': 'connecting',
                    'stage': f'Connecting to GitHub ({repo_count} repos)...',
                    'total_items': 0,
                    'processed_items': 0,
                    'failed_items': 0,
                    'repositories': repositories,
                    'current_repo_index': 0
                }
            }
            connector.status = ConnectorStatus.SYNCING
            db.commit()
            print(f"[GitHub] Saved sync_id to DB, connector status: {connector.status}")

            print(f"[GitHub] Starting background sync, sync_id={sync_id}, repositories={repositories}")

            # Start background thread with repositories array
            thread = threading.Thread(
                target=_run_github_sync_multi,
                args=(tenant_id, connector_id, sync_id, repositories, max_files, max_files_to_analyze, notify_email),
                daemon=True
            )
            thread.start()

            return jsonify({
                "success": True,
                "sync_id": sync_id,
                "message": f"GitHub sync started for {repo_count} repositories",
                "connector_id": connector_id,
                "repositories": repositories
            })

        finally:
            db.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SYNC STATUS (for polling fallback - fixes email notification)
# ============================================================================

@github_bp.route('/sync/status', methods=['GET'])
@require_auth
def get_sync_status():
    """
    Get current sync status for GitHub.
    Required for frontend polling fallback when SSE fails.
    Fixes "Email me when done" not working for GitHub.
    """
    db = get_db()
    try:
        progress_service = get_sync_progress_service()

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GITHUB,
            Connector.is_active == True
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "GitHub not connected"}), 404

        settings = connector.settings or {}
        sync_id = settings.get('current_sync_id')
        sync_progress_data = settings.get('sync_progress', {})

        # Try in-memory progress first
        if sync_id:
            progress = progress_service.get_progress(sync_id)
            if progress:
                return jsonify({
                    "success": True,
                    "status": {
                        "status": progress.get('status', 'syncing'),
                        "progress": int((progress.get('processed_items', 0) / max(progress.get('total_items', 1), 1)) * 100),
                        "documents_found": progress.get('total_items', 0),
                        "documents_parsed": progress.get('processed_items', 0),
                        "current_file": progress.get('stage', ''),
                        "error": progress.get('error_message')
                    }
                })

        # Fallback to database
        if connector.status == ConnectorStatus.SYNCING:
            return jsonify({
                "success": True,
                "status": {
                    "status": sync_progress_data.get('status', 'syncing'),
                    "progress": sync_progress_data.get('progress', 0),
                    "documents_found": sync_progress_data.get('total_items', 0),
                    "documents_parsed": sync_progress_data.get('processed_items', 0),
                    "current_file": sync_progress_data.get('stage', 'Syncing...'),
                    "error": None
                }
            })

        # No active sync
        return jsonify({
            "success": True,
            "status": {
                "status": "completed" if connector.last_sync_at else "idle",
                "progress": 100 if connector.last_sync_at else 0,
                "documents_found": connector.last_sync_items_count or 0,
                "documents_parsed": connector.last_sync_items_count or 0,
                "current_file": None,
                "error": connector.error_message
            }
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# DISCONNECT
# ============================================================================

def _get_github_disconnect_counts(db, tenant_id: str, connector_id: str):
    """
    Get counts of items that will be deleted when disconnecting GitHub.
    Returns dict with document_count, gap_count, chunk_count.
    """
    from database.models import DocumentChunk, KnowledgeGap

    # Get all document IDs for this connector
    doc_ids = [d.id for d in db.query(Document.id).filter(
        Document.tenant_id == tenant_id,
        Document.connector_id == connector_id
    ).all()]

    document_count = len(doc_ids)

    # Count chunks
    chunk_count = db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(doc_ids)
    ).count() if doc_ids else 0

    # Count knowledge gaps that EXCLUSIVELY reference these documents
    gap_count = 0
    if doc_ids:
        doc_ids_set = set(doc_ids)
        all_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id
        ).all()

        for gap in all_gaps:
            related_docs = gap.related_document_ids or []
            if related_docs and set(related_docs).issubset(doc_ids_set):
                gap_count += 1

    return {
        "document_count": document_count,
        "chunk_count": chunk_count,
        "gap_count": gap_count
    }


def _cascade_delete_github_data(db, tenant_id: str, connector_id: str):
    """
    Delete all data associated with GitHub connector:
    1. Delete embeddings from Pinecone
    2. Delete knowledge gaps that exclusively reference these documents
    3. Delete document chunks
    4. Delete documents

    Returns dict with deletion counts.
    """
    from database.models import DocumentChunk, KnowledgeGap

    # Get all documents for this connector
    documents = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.connector_id == connector_id
    ).all()

    doc_ids = [doc.id for doc in documents]

    if not doc_ids:
        return {"documents_deleted": 0, "gaps_deleted": 0, "chunks_deleted": 0, "embeddings_deleted": 0}

    print(f"[GitHub Disconnect] Cascade deleting {len(doc_ids)} documents for connector {connector_id}")

    # Step 1: Delete from Pinecone
    embeddings_deleted = 0
    try:
        from services.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()
        result = embedding_service.delete_document_embeddings(doc_ids, tenant_id, db)
        embeddings_deleted = result.get('deleted', 0) if result.get('success') else 0
        print(f"[GitHub Disconnect] Deleted {embeddings_deleted} embeddings from Pinecone")
    except Exception as e:
        print(f"[GitHub Disconnect] Warning: Failed to delete Pinecone embeddings: {e}")

    # Step 2: Delete knowledge gaps that reference these documents
    doc_ids_set = set(str(d) for d in doc_ids)  # Ensure string comparison
    gaps_to_delete = []
    all_gaps = db.query(KnowledgeGap).filter(
        KnowledgeGap.tenant_id == tenant_id
    ).all()

    for gap in all_gaps:
        related_docs = gap.related_document_ids or []
        if not related_docs:
            # Gap has no related docs - orphaned, delete it
            gaps_to_delete.append(gap.id)
        else:
            # Convert to strings for comparison
            related_docs_set = set(str(d) for d in related_docs)
            # Delete if ALL related docs are from this connector
            if related_docs_set.issubset(doc_ids_set):
                gaps_to_delete.append(gap.id)
            # Also check if any related doc is being deleted
            elif related_docs_set.intersection(doc_ids_set):
                remaining_docs = related_docs_set - doc_ids_set
                if not remaining_docs:
                    gaps_to_delete.append(gap.id)

    gaps_deleted = 0
    if gaps_to_delete:
        gaps_deleted = db.query(KnowledgeGap).filter(
            KnowledgeGap.id.in_(gaps_to_delete)
        ).delete(synchronize_session=False)
        print(f"[GitHub Disconnect] Deleted {gaps_deleted} knowledge gaps")

    # Step 3: Delete document chunks
    chunks_deleted = db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(doc_ids)
    ).delete(synchronize_session=False)
    print(f"[GitHub Disconnect] Deleted {chunks_deleted} document chunks")

    # Step 4: Delete documents
    documents_deleted = db.query(Document).filter(
        Document.id.in_(doc_ids)
    ).delete(synchronize_session=False)
    print(f"[GitHub Disconnect] Deleted {documents_deleted} documents")

    return {
        "documents_deleted": documents_deleted,
        "gaps_deleted": gaps_deleted,
        "chunks_deleted": chunks_deleted,
        "embeddings_deleted": embeddings_deleted
    }


@github_bp.route('/disconnect/preview', methods=['GET'])
@require_auth
def disconnect_github_preview():
    """
    Preview what will be deleted when disconnecting GitHub.
    Returns counts of documents, knowledge gaps, etc.
    """
    db = get_db()
    try:
        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GITHUB
        ).first()

        if not connector:
            return jsonify({
                "success": False,
                "error": "GitHub not connected"
            }), 400

        counts = _get_github_disconnect_counts(db, g.tenant_id, connector.id)

        return jsonify({
            "success": True,
            "connector_type": "github",
            "counts": counts,
            "warning": f"Disconnecting will permanently delete {counts['document_count']} documents, {counts['gap_count']} knowledge gaps, and all associated embeddings."
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()


@github_bp.route('/disconnect', methods=['POST'])
@require_auth
def disconnect_github():
    """
    Disconnect GitHub integration and delete all associated data.

    This will:
    1. Delete all documents from this integration
    2. Delete embeddings from Pinecone
    3. Delete knowledge gaps that exclusively reference these documents
    4. Mark the connector as disconnected

    Request body (optional):
    {
        "confirm": true  // Required to proceed with deletion
    }
    """
    db = get_db()
    try:
        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GITHUB
        ).first()

        if not connector:
            return jsonify({
                "success": False,
                "error": "GitHub not connected"
            }), 400

        data = request.get_json() or {}
        confirmed = data.get('confirm', False)

        # Get counts first
        counts = _get_github_disconnect_counts(db, g.tenant_id, connector.id)

        # If there's data and not confirmed, return warning
        if (counts['document_count'] > 0 or counts['gap_count'] > 0) and not confirmed:
            return jsonify({
                "success": False,
                "requires_confirmation": True,
                "counts": counts,
                "warning": f"This will permanently delete {counts['document_count']} documents and {counts['gap_count']} knowledge gaps. Send confirm: true to proceed."
            }), 400

        # Cascade delete all data
        deletion_result = _cascade_delete_github_data(db, g.tenant_id, connector.id)

        # Disconnect the connector
        connector.status = ConnectorStatus.DISCONNECTED
        connector.access_token = None
        connector.refresh_token = None
        connector.updated_at = datetime.now(timezone.utc)
        db.commit()

        return jsonify({
            "success": True,
            "message": "GitHub disconnected",
            "deleted": deletion_result
        })

    except Exception as e:
        db.rollback()
        import traceback
        print(f"[GitHub] Error disconnecting: {str(e)}")
        print(f"[GitHub] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    finally:
        db.close()
