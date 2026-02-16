"""
Website Generator Service v3
Generates professional research lab websites using templates.

Uses GPT for data extraction and synthesis, then renders via template engine.
Much faster and more consistent than pure GPT generation.
"""

import os
import json
import logging
import zipfile
import shutil
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from io import BytesIO

from openai import AzureOpenAI
from sqlalchemy.orm import Session

from services.website_template_engine import (
    WebsiteTemplateEngine,
    WebsiteData,
    WebsiteConfig,
    generate_website_from_data
)
from services.image_repository import get_image_repository

logger = logging.getLogger(__name__)

# Azure OpenAI Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_API_VERSION = os.getenv("AZURE_API_VERSION", "2024-12-01-preview")
AZURE_CHAT_DEPLOYMENT = os.getenv("AZURE_CHAT_DEPLOYMENT", "gpt-5-chat")

# Output directory for generated websites
WEBSITES_DIR = Path(__file__).parent.parent / "generated_websites"


@dataclass
class LabInfo:
    """Extracted information about a research lab"""
    name: str = ""
    tagline: str = ""
    description: str = ""
    research_areas: List[Dict[str, str]] = field(default_factory=list)
    team_members: List[Dict[str, str]] = field(default_factory=list)
    publications: List[Dict[str, str]] = field(default_factory=list)
    projects: List[Dict[str, str]] = field(default_factory=list)
    contact_info: Dict[str, str] = field(default_factory=dict)
    news_updates: List[Dict[str, str]] = field(default_factory=list)
    funding_sources: List[str] = field(default_factory=list)
    collaborators: List[str] = field(default_factory=list)
    institution: str = ""


@dataclass
class WebsiteGenerationResult:
    """Result of website generation"""
    success: bool
    website_id: Optional[str] = None
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    html_content: Optional[str] = None
    lab_info: Optional[LabInfo] = None
    error: Optional[str] = None
    stats: Dict[str, int] = field(default_factory=dict)
    generation_time_ms: int = 0


class WebsiteGeneratorService:
    """
    Service for generating research lab websites.

    Workflow:
    1. Extract lab information from database documents using GPT
    2. Structure the data for the template engine
    3. Generate HTML using professional templates
    4. Save to file system and return preview/download URLs
    """

    # Prompt for extracting structured info from documents
    SYNTHESIS_PROMPT = """You are helping create content for a research lab website.
Based on the following documents from the lab's knowledge base, extract and synthesize information.

DOCUMENTS:
{context}

LAB NAME: {lab_name}
{focus_areas_instruction}

Please extract and structure the following information in JSON format:
{{
    "name": "Full lab name",
    "tagline": "A compelling one-line description (max 10 words)",
    "description": "2-3 paragraph overview of the lab's mission, vision, and impact. Make it engaging and professional.",
    "institution": "University or institution name if found",
    "research_areas": [
        {{"name": "Area name", "description": "2-3 sentence description of this research focus"}}
    ],
    "team_members": [
        {{"name": "Full name", "role": "Position/Title", "bio": "1-2 sentence bio", "email": "if found"}}
    ],
    "publications": [
        {{"title": "Publication title", "authors": "Author list", "venue": "Journal/Conference", "year": "Year"}}
    ],
    "projects": [
        {{"name": "Project name", "description": "2-3 sentence description", "status": "ongoing or completed"}}
    ],
    "contact_info": {{"email": "", "phone": "", "address": "", "office": ""}},
    "news_updates": [
        {{"title": "Update title", "date": "YYYY-MM-DD or descriptive date", "summary": "Brief summary"}}
    ],
    "funding_sources": ["List of funding agencies or grants"],
    "collaborators": ["List of collaborating institutions or labs"]
}}

IMPORTANT:
- Extract as much REAL information as you can find from the documents
- For research_areas, provide actual descriptions based on the content
- For team_members, include everyone you can identify with their actual roles
- Do NOT make up fake information - leave arrays empty if data not found
- Make the description and tagline compelling but accurate
"""

    def __init__(self, tenant_id: str, db: Session):
        """Initialize the website generator service."""
        self.tenant_id = tenant_id
        self.db = db
        self._openai_client = None

        # Ensure output directory exists
        WEBSITES_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None:
            self._openai_client = AzureOpenAI(
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                api_version=AZURE_API_VERSION
            )
        return self._openai_client

    def extract_lab_info(
        self,
        lab_name: str,
        focus_areas: Optional[List[str]] = None,
        max_documents: int = 100
    ) -> LabInfo:
        """
        Extract lab information from the database documents using GPT.
        """
        from database.models import Document

        logger.info(f"[WebsiteGen] Extracting lab info for '{lab_name}' (tenant: {self.tenant_id})")

        # Query documents from database for this tenant
        documents = self.db.query(Document).filter(
            Document.tenant_id == self.tenant_id
        ).order_by(Document.created_at.desc()).limit(max_documents).all()

        logger.info(f"[WebsiteGen] Found {len(documents)} documents in database")

        if not documents:
            logger.warning("[WebsiteGen] No documents found in database")
            return LabInfo(name=lab_name, research_areas=[
                {"name": area, "description": ""} for area in (focus_areas or [])
            ])

        # Build context from documents
        context_parts = []
        total_chars = 0
        max_context_chars = 80000

        for doc in documents:
            title = doc.title or "Untitled"
            content = doc.content or ""

            # Use structured summary if available
            if doc.structured_summary:
                summary_text = json.dumps(doc.structured_summary, indent=2)[:2000]
                chunk = f"[{doc.source_type or 'DOC'}] {title}:\nSummary: {summary_text}\n"
            else:
                chunk = f"[{doc.source_type or 'DOC'}] {title}:\n{content[:3000]}\n"

            if total_chars + len(chunk) > max_context_chars:
                break

            context_parts.append(chunk)
            total_chars += len(chunk)

        context = "\n---\n".join(context_parts)

        logger.info(f"[WebsiteGen] Built context with {len(context_parts)} documents ({total_chars} chars)")

        # Use LLM to synthesize information
        try:
            lab_info = self._synthesize_with_llm(lab_name, context, focus_areas)
        except Exception as e:
            logger.error(f"[WebsiteGen] LLM synthesis error: {e}")
            import traceback
            traceback.print_exc()
            lab_info = LabInfo(
                name=lab_name,
                research_areas=[{"name": area, "description": ""} for area in (focus_areas or [])]
            )

        return lab_info

    def _synthesize_with_llm(
        self,
        lab_name: str,
        context: str,
        focus_areas: Optional[List[str]] = None
    ) -> LabInfo:
        """Use LLM to synthesize structured lab information from context."""

        focus_instruction = ""
        if focus_areas:
            focus_instruction = f"\nFocus Areas to emphasize: {', '.join(focus_areas)}"

        prompt = self.SYNTHESIS_PROMPT.format(
            context=context,
            lab_name=lab_name,
            focus_areas_instruction=focus_instruction
        )

        logger.info(f"[WebsiteGen] Calling LLM for synthesis ({len(prompt)} chars)")

        response = self.openai_client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": "You are a research communications expert. Extract and structure lab information accurately. Output valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=4000,
            temperature=0.3,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content

        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"[WebsiteGen] JSON parse error: {e}")
            return LabInfo(name=lab_name)

        # Build LabInfo from response
        lab_info = LabInfo(
            name=data.get('name', lab_name),
            tagline=data.get('tagline', ''),
            description=data.get('description', ''),
            institution=data.get('institution', ''),
            research_areas=data.get('research_areas', []),
            team_members=data.get('team_members', []),
            publications=data.get('publications', []),
            projects=data.get('projects', []),
            contact_info=data.get('contact_info', {}),
            news_updates=data.get('news_updates', []),
            funding_sources=data.get('funding_sources', []),
            collaborators=data.get('collaborators', [])
        )

        logger.info(f"[WebsiteGen] Extracted: {len(lab_info.team_members)} team members, "
                    f"{len(lab_info.publications)} publications, {len(lab_info.projects)} projects, "
                    f"{len(lab_info.research_areas)} research areas")

        return lab_info

    def generate_website_html(
        self,
        lab_info: LabInfo,
        theme: str = "blue",
        avatar_style: str = "notionists"
    ) -> str:
        """Generate website HTML using the template engine."""

        # Convert LabInfo to WebsiteData
        website_data = WebsiteData(
            lab_name=lab_info.name,
            tagline=lab_info.tagline,
            description=lab_info.description,
            research_areas=lab_info.research_areas,
            team_members=lab_info.team_members,
            publications=lab_info.publications,
            projects=lab_info.projects,
            news_updates=lab_info.news_updates,
            contact_info=lab_info.contact_info,
            funding_sources=lab_info.funding_sources,
            collaborators=lab_info.collaborators,
            institution=lab_info.institution
        )

        # Create config
        config = WebsiteConfig(
            theme=theme,
            avatar_style=avatar_style,
            show_hero_image=True
        )

        # Generate HTML using template engine
        logger.info(f"[WebsiteGen] Generating HTML with template engine (theme: {theme})")
        html_content = generate_website_from_data(website_data, config)

        logger.info(f"[WebsiteGen] Generated HTML ({len(html_content)} chars)")

        return html_content

    def save_website(
        self,
        html_content: str,
        lab_name: str
    ) -> tuple[str, str]:
        """
        Save the generated website to the filesystem.

        Returns:
            Tuple of (website_id, file_path)
        """
        # Generate unique website ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_slug = "".join(c if c.isalnum() else "_" for c in lab_name.lower())[:30]
        website_id = f"{name_slug}_{timestamp}"

        # Create website directory
        website_dir = WEBSITES_DIR / website_id
        website_dir.mkdir(parents=True, exist_ok=True)

        # Save HTML file
        html_path = website_dir / "index.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"[WebsiteGen] Saved website to {html_path}")

        return website_id, str(html_path)

    def create_zip(self, website_id: str) -> BytesIO:
        """
        Create a ZIP file of the generated website.

        Returns:
            BytesIO object containing the ZIP file
        """
        website_dir = WEBSITES_DIR / website_id

        if not website_dir.exists():
            raise FileNotFoundError(f"Website {website_id} not found")

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in website_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(website_dir)
                    zip_file.write(file_path, arcname)

        zip_buffer.seek(0)
        return zip_buffer

    def generate_website(
        self,
        lab_name: str,
        focus_areas: Optional[List[str]] = None,
        image_urls: Optional[List[str]] = None,
        custom_instructions: Optional[str] = None,
        theme: str = "blue",
        avatar_style: str = "notionists"
    ) -> WebsiteGenerationResult:
        """
        Main method to generate a complete research lab website.

        Args:
            lab_name: Name of the research lab
            focus_areas: Optional list of research focus areas
            image_urls: Optional list of custom image URLs (not used with template engine)
            custom_instructions: Optional additional instructions (not used with template engine)
            theme: Color theme (blue, green, purple, dark, minimal)
            avatar_style: Avatar style (notionists, lorelei, avataaars, personas, micah)

        Returns:
            WebsiteGenerationResult with the generated HTML and file paths
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"[WebsiteGen] Starting website generation for '{lab_name}' (theme: {theme})")

            # Step 1: Extract lab information from database
            lab_info = self.extract_lab_info(
                lab_name=lab_name,
                focus_areas=focus_areas
            )

            stats = {
                "team_members": len(lab_info.team_members),
                "publications": len(lab_info.publications),
                "projects": len(lab_info.projects),
                "research_areas": len(lab_info.research_areas),
                "news_updates": len(lab_info.news_updates)
            }

            # Step 2: Generate HTML using template engine
            html_content = self.generate_website_html(
                lab_info=lab_info,
                theme=theme,
                avatar_style=avatar_style
            )

            # Step 3: Save to filesystem
            website_id, file_path = self.save_website(
                html_content=html_content,
                lab_name=lab_name
            )

            # Generate URLs
            preview_url = f"/api/website/preview/{website_id}"
            download_url = f"/api/website/download/{website_id}"

            generation_time = int((time.time() - start_time) * 1000)
            logger.info(f"[WebsiteGen] Successfully generated website: {website_id} in {generation_time}ms")

            return WebsiteGenerationResult(
                success=True,
                website_id=website_id,
                preview_url=preview_url,
                download_url=download_url,
                html_content=html_content,
                lab_info=lab_info,
                stats=stats,
                generation_time_ms=generation_time
            )

        except Exception as e:
            logger.error(f"[WebsiteGen] Generation error: {e}")
            import traceback
            traceback.print_exc()

            return WebsiteGenerationResult(
                success=False,
                error=str(e)
            )


def get_website_generator(tenant_id: str, db: Session) -> WebsiteGeneratorService:
    """Factory function to get a website generator instance."""
    return WebsiteGeneratorService(tenant_id, db)


def get_websites_dir() -> Path:
    """Get the directory where generated websites are stored."""
    WEBSITES_DIR.mkdir(parents=True, exist_ok=True)
    return WEBSITES_DIR
