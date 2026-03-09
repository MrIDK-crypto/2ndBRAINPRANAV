"""
NotebookLM Service
Wraps notebooklm-py to generate training videos and slide decks
from the user's knowledge base documents.

Auth: Uses NOTEBOOKLM_AUTH_JSON env var (cookie-based, no Playwright needed at runtime).
"""

import os
import json
import asyncio
import logging
import tempfile
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

import boto3

from database.models import (
    SessionLocal, TrainingGuide, TrainingGuideStatus, Document, utc_now
)

logger = logging.getLogger(__name__)


def _get_s3_client():
    """Get S3 client if configured."""
    if os.getenv("AWS_S3_BUCKET"):
        return boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-2"))
    return None


def _upload_to_s3(local_path: str, s3_key: str) -> Optional[str]:
    """Upload file to S3, return URL or None."""
    bucket = os.getenv("AWS_S3_BUCKET")
    client = _get_s3_client()
    if not client or not bucket:
        return None
    try:
        client.upload_file(local_path, bucket, s3_key)
        region = os.getenv("AWS_REGION", "us-east-2")
        return f"https://{bucket}.s3.{region}.amazonaws.com/{s3_key}"
    except Exception as e:
        logger.error(f"S3 upload failed: {e}")
        return None


def _load_auth_from_secrets_manager() -> Optional[str]:
    """Load NotebookLM auth JSON from AWS Secrets Manager."""
    try:
        client = boto3.client("secretsmanager", region_name=os.getenv("AWS_REGION", "us-east-2"))
        resp = client.get_secret_value(SecretId="secondbrain/notebooklm-auth")
        return resp["SecretString"]
    except Exception as e:
        logger.warning(f"Could not load from Secrets Manager: {e}")
        return None


def _ensure_auth_env():
    """Ensure NOTEBOOKLM_AUTH_JSON is set. Try Secrets Manager if not."""
    if os.getenv("NOTEBOOKLM_AUTH_JSON"):
        return True
    # Try loading from Secrets Manager
    auth_json = _load_auth_from_secrets_manager()
    if auth_json:
        os.environ["NOTEBOOKLM_AUTH_JSON"] = auth_json
        logger.info("Loaded NotebookLM auth from Secrets Manager")
        return True
    # Try local file
    storage_file = os.path.expanduser("~/.notebooklm/storage_state.json")
    if os.path.exists(storage_file):
        logger.info("Using local NotebookLM storage state file")
        return True
    logger.error("No NotebookLM auth found (env, Secrets Manager, or local file)")
    return False


class NotebookLMService:
    """Service for generating training content via Google NotebookLM."""

    def __init__(self):
        self._auth_available = _ensure_auth_env()

    @property
    def is_available(self) -> bool:
        return self._auth_available

    async def _get_client(self):
        """Get an authenticated NotebookLM client."""
        from notebooklm import NotebookLMClient
        return await NotebookLMClient.from_storage()

    async def _create_notebook_with_sources(
        self,
        title: str,
        documents: list,
    ) -> Tuple[str, list]:
        """
        Create a NotebookLM notebook and add document content as sources.
        Returns (notebook_id, source_ids).
        """
        async with await self._get_client() as client:
            # Create notebook
            notebook = await client.notebooks.create(title=title)
            notebook_id = notebook.id
            logger.info(f"Created NotebookLM notebook: {notebook_id}")

            source_ids = []
            for doc in documents:
                try:
                    content = doc.get("content", "")
                    doc_title = doc.get("title", "Untitled")
                    if not content or len(content.strip()) < 50:
                        logger.warning(f"Skipping doc '{doc_title}' — too short")
                        continue

                    # Truncate to ~500K chars (NotebookLM limit per source)
                    if len(content) > 500000:
                        content = content[:500000]

                    source = await client.sources.add_text(
                        notebook_id=notebook_id,
                        title=doc_title,
                        content=content,
                        wait=True,
                    )
                    source_ids.append(source.id)
                    logger.info(f"Added source: {doc_title} ({len(content)} chars)")
                except Exception as e:
                    logger.error(f"Failed to add source '{doc.get('title')}': {e}")

            return notebook_id, source_ids

    async def _generate_video(
        self,
        notebook_id: str,
        source_ids: list,
        instructions: Optional[str] = None,
        video_style: str = "classic",
        video_format: str = "explainer",
    ) -> Optional[str]:
        """
        Generate a video overview and download it.
        Returns local path to downloaded MP4.
        """
        from notebooklm.rpc.types import VideoStyle, VideoFormat

        style_map = {
            "auto": VideoStyle.AUTO_SELECT,
            "classic": VideoStyle.CLASSIC,
            "whiteboard": VideoStyle.WHITEBOARD,
            "kawaii": VideoStyle.KAWAII,
            "anime": VideoStyle.ANIME,
            "watercolor": VideoStyle.WATERCOLOR,
            "retro_print": VideoStyle.RETRO_PRINT,
            "heritage": VideoStyle.HERITAGE,
            "paper_craft": VideoStyle.PAPER_CRAFT,
        }
        format_map = {
            "explainer": VideoFormat.EXPLAINER,
            "brief": VideoFormat.BRIEF,
        }

        async with await self._get_client() as client:
            status = await client.artifacts.generate_video(
                notebook_id=notebook_id,
                source_ids=source_ids if source_ids else None,
                instructions=instructions,
                video_style=style_map.get(video_style, VideoStyle.CLASSIC),
                video_format=format_map.get(video_format, VideoFormat.EXPLAINER),
            )
            logger.info(f"Video generation started, task_id: {status.task_id}")

            # Wait for completion (up to 15 minutes)
            result = await client.artifacts.wait_for_completion(
                notebook_id=notebook_id,
                task_id=status.task_id,
                timeout=900,
                poll_interval=10,
            )
            logger.info(f"Video generation complete: {result}")

            # Download
            output_path = tempfile.mktemp(suffix=".mp4")
            await client.artifacts.download_video(
                notebook_id=notebook_id,
                output_path=output_path,
                artifact_id=result.artifact_id if hasattr(result, "artifact_id") else None,
            )
            logger.info(f"Video downloaded to {output_path}")
            return output_path

    async def _generate_slides(
        self,
        notebook_id: str,
        source_ids: list,
        instructions: Optional[str] = None,
        slide_format: str = "detailed_deck",
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate slide deck and download as PPTX and PDF.
        Returns (pptx_path, pdf_path).
        """
        from notebooklm.rpc.types import SlideDeckFormat

        format_map = {
            "detailed_deck": SlideDeckFormat.DETAILED_DECK,
            "presenter_slides": SlideDeckFormat.PRESENTER_SLIDES,
        }

        async with await self._get_client() as client:
            status = await client.artifacts.generate_slide_deck(
                notebook_id=notebook_id,
                source_ids=source_ids if source_ids else None,
                instructions=instructions,
                slide_format=format_map.get(slide_format, SlideDeckFormat.DETAILED_DECK),
            )
            logger.info(f"Slide generation started, task_id: {status.task_id}")

            result = await client.artifacts.wait_for_completion(
                notebook_id=notebook_id,
                task_id=status.task_id,
                timeout=600,
                poll_interval=8,
            )
            logger.info(f"Slide generation complete: {result}")

            artifact_id = result.artifact_id if hasattr(result, "artifact_id") else None

            # Download PPTX
            pptx_path = tempfile.mktemp(suffix=".pptx")
            try:
                await client.artifacts.download_slide_deck(
                    notebook_id=notebook_id,
                    output_path=pptx_path,
                    artifact_id=artifact_id,
                    output_format="pptx",
                )
                logger.info(f"PPTX downloaded to {pptx_path}")
            except Exception as e:
                logger.error(f"PPTX download failed: {e}")
                pptx_path = None

            # Download PDF
            pdf_path = tempfile.mktemp(suffix=".pdf")
            try:
                await client.artifacts.download_slide_deck(
                    notebook_id=notebook_id,
                    output_path=pdf_path,
                    artifact_id=artifact_id,
                    output_format="pdf",
                )
                logger.info(f"PDF downloaded to {pdf_path}")
            except Exception as e:
                logger.error(f"PDF download failed: {e}")
                pdf_path = None

            return pptx_path, pdf_path

    def generate_content_async(self, guide_id: str, tenant_id: str):
        """
        Kick off content generation in a background thread.
        Creates NotebookLM notebook, generates video + slides, uploads to S3.
        """
        thread = threading.Thread(
            target=self._run_generation,
            args=(guide_id, tenant_id),
            daemon=True,
        )
        thread.start()
        return thread

    def _run_generation(self, guide_id: str, tenant_id: str):
        """Background thread that runs the async generation pipeline."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._generate_pipeline(guide_id, tenant_id))
        except Exception as e:
            logger.error(f"Generation pipeline failed: {e}", exc_info=True)
            # Mark as failed
            db = SessionLocal()
            try:
                guide = db.query(TrainingGuide).filter_by(id=guide_id).first()
                if guide:
                    guide.status = TrainingGuideStatus.FAILED
                    guide.error_message = str(e)[:500]
                    db.commit()
            finally:
                db.close()
        finally:
            loop.close()

    async def _generate_pipeline(self, guide_id: str, tenant_id: str):
        """Full generation pipeline: create notebook → add sources → generate video + slides → upload."""
        db = SessionLocal()
        try:
            guide = db.query(TrainingGuide).filter_by(id=guide_id).first()
            if not guide:
                logger.error(f"Training guide {guide_id} not found")
                return

            guide.status = TrainingGuideStatus.GENERATING
            guide.started_at = utc_now()
            guide.progress_percent = 5
            guide.current_step = "Preparing documents..."
            db.commit()

            # Fetch document content
            doc_ids = guide.source_document_ids or []
            documents = []
            for doc_id in doc_ids:
                doc = db.query(Document).filter_by(id=doc_id, tenant_id=tenant_id).first()
                if doc:
                    content = doc.content or ""
                    if doc.structured_summary:
                        summary = doc.structured_summary
                        if isinstance(summary, dict) and summary.get("summary"):
                            # Prepend summary for better context
                            content = f"SUMMARY: {summary['summary']}\n\n{content}"
                    documents.append({
                        "title": doc.title or f"Document {doc_id[:8]}",
                        "content": content,
                    })

            if not documents:
                guide.status = TrainingGuideStatus.FAILED
                guide.error_message = "No documents found for the selected IDs"
                db.commit()
                return

            logger.info(f"Processing {len(documents)} documents for guide '{guide.title}'")

            # Step 1: Create NotebookLM notebook + add sources
            guide.progress_percent = 10
            guide.current_step = "Creating NotebookLM notebook..."
            db.commit()

            notebook_id, source_ids = await self._create_notebook_with_sources(
                title=guide.title,
                documents=documents,
            )
            guide.notebooklm_notebook_id = notebook_id
            guide.progress_percent = 25
            guide.current_step = f"Added {len(source_ids)} sources to notebook"
            db.commit()

            if not source_ids:
                guide.status = TrainingGuideStatus.FAILED
                guide.error_message = "Failed to add any sources to NotebookLM"
                db.commit()
                return

            # Build instructions from outline + user instructions
            instructions = ""
            if guide.content_outline:
                instructions += f"Follow this outline:\n{guide.content_outline}\n\n"
            if guide.instructions:
                instructions += guide.instructions
            instructions = instructions.strip() or None

            # Step 2: Generate video
            guide.progress_percent = 30
            guide.current_step = "Generating video overview (this may take several minutes)..."
            db.commit()

            video_path = None
            try:
                video_path = await self._generate_video(
                    notebook_id=notebook_id,
                    source_ids=source_ids,
                    instructions=instructions,
                    video_style=guide.video_style or "classic",
                    video_format=guide.video_format or "explainer",
                )
            except Exception as e:
                logger.error(f"Video generation failed: {e}", exc_info=True)
                guide.error_message = f"Video generation failed: {str(e)[:200]}"
                db.commit()

            guide.progress_percent = 65
            guide.current_step = "Generating slide deck..."
            db.commit()

            # Step 3: Generate slides
            pptx_path = None
            pdf_path = None
            try:
                pptx_path, pdf_path = await self._generate_slides(
                    notebook_id=notebook_id,
                    source_ids=source_ids,
                    instructions=instructions,
                    slide_format=guide.slide_format or "detailed_deck",
                )
            except Exception as e:
                logger.error(f"Slide generation failed: {e}", exc_info=True)
                if not guide.error_message:
                    guide.error_message = f"Slide generation failed: {str(e)[:200]}"
                db.commit()

            # Step 4: Upload to S3
            guide.progress_percent = 85
            guide.current_step = "Uploading to cloud storage..."
            db.commit()

            s3_prefix = f"training-guides/{tenant_id}/{guide_id}"

            if video_path and os.path.exists(video_path):
                s3_url = _upload_to_s3(video_path, f"{s3_prefix}/video.mp4")
                if s3_url:
                    guide.video_path = s3_url
                else:
                    guide.video_path = video_path  # Keep local path as fallback
                guide.video_size_bytes = os.path.getsize(video_path)
                if s3_url:
                    os.remove(video_path)

            if pptx_path and os.path.exists(pptx_path):
                s3_url = _upload_to_s3(pptx_path, f"{s3_prefix}/slides.pptx")
                guide.slides_path = s3_url or pptx_path
                if s3_url:
                    os.remove(pptx_path)

            if pdf_path and os.path.exists(pdf_path):
                s3_url = _upload_to_s3(pdf_path, f"{s3_prefix}/slides.pdf")
                guide.slides_pdf_path = s3_url or pdf_path
                if s3_url:
                    os.remove(pdf_path)

            # Done
            if guide.video_path or guide.slides_path:
                guide.status = TrainingGuideStatus.COMPLETED
                guide.progress_percent = 100
                guide.current_step = "Complete"
                guide.completed_at = utc_now()
            else:
                guide.status = TrainingGuideStatus.FAILED
                guide.error_message = guide.error_message or "No outputs were generated"

            db.commit()
            logger.info(f"Training guide '{guide.title}' generation complete: {guide.status.value}")

        except Exception as e:
            logger.error(f"Pipeline error: {e}", exc_info=True)
            try:
                guide = db.query(TrainingGuide).filter_by(id=guide_id).first()
                if guide:
                    guide.status = TrainingGuideStatus.FAILED
                    guide.error_message = str(e)[:500]
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    async def cleanup_notebook(self, notebook_id: str):
        """Delete a NotebookLM notebook after generation is complete."""
        try:
            async with await self._get_client() as client:
                await client.notebooks.delete(notebook_id)
                logger.info(f"Deleted NotebookLM notebook: {notebook_id}")
        except Exception as e:
            logger.warning(f"Failed to cleanup notebook {notebook_id}: {e}")


# Module-level singleton
_service: Optional[NotebookLMService] = None


def get_notebooklm_service() -> NotebookLMService:
    global _service
    if _service is None:
        _service = NotebookLMService()
    return _service
