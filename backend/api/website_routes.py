"""
Website Generator API Routes v3
REST endpoints for generating research lab websites using templates.

Supports customization options:
- theme: blue, green, purple, dark, minimal
- avatar_style: notionists, lorelei, avataaars, personas, micah
"""

from flask import Blueprint, request, jsonify, g, send_file, Response
from dataclasses import asdict
from pathlib import Path
import os
import re
import json

from services.auth_service import require_auth


def _validate_website_id(website_id: str) -> bool:
    """Validate website_id to prevent path traversal attacks."""
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', website_id))
from services.website_generator_service import (
    WebsiteGeneratorService,
    get_website_generator,
    get_websites_dir,
    LabInfo
)
from database.models import get_db


# Create blueprint
website_bp = Blueprint('website', __name__, url_prefix='/api/website')


# ============================================================================
# GENERATE WEBSITE
# ============================================================================

@website_bp.route('/generate', methods=['POST'])
@require_auth
def generate_website():
    """
    Generate a research lab website using professional templates.

    Extracts information from the user's knowledge base (emails, Slack,
    documents, etc.) and generates a complete HTML/CSS/JS website.

    Request body:
    {
        "lab_name": "Smith Lab" (required),
        "focus_areas": ["Machine Learning", "NLP"] (optional),
        "theme": "blue" (optional, default: "blue"),
        "avatar_style": "notionists" (optional, default: "notionists")
    }

    Available themes: blue, green, purple, dark, minimal
    Available avatar styles: notionists, lorelei, avataaars, personas, micah

    Response:
    {
        "success": true,
        "website_id": "smith_lab_20260213_154532",
        "preview_url": "/api/website/preview/smith_lab_20260213_154532",
        "download_url": "/api/website/download/smith_lab_20260213_154532",
        "download_zip_url": "/api/website/download-zip/smith_lab_20260213_154532",
        "stats": {
            "team_members": 5,
            "publications": 12,
            "projects": 3,
            "research_areas": 4,
            "news_updates": 2
        },
        "generation_time_ms": 3500
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        lab_name = data.get('lab_name')
        if not lab_name:
            return jsonify({
                "success": False,
                "error": "lab_name is required"
            }), 400

        focus_areas = data.get('focus_areas', [])
        theme = data.get('theme', 'blue')
        avatar_style = data.get('avatar_style', 'notionists')

        # Validate theme
        valid_themes = ['blue', 'green', 'purple', 'dark', 'minimal']
        if theme not in valid_themes:
            return jsonify({
                "success": False,
                "error": f"Invalid theme. Valid options: {', '.join(valid_themes)}"
            }), 400

        # Validate avatar style
        valid_avatar_styles = ['notionists', 'lorelei', 'avataaars', 'personas', 'micah']
        if avatar_style not in valid_avatar_styles:
            return jsonify({
                "success": False,
                "error": f"Invalid avatar_style. Valid options: {', '.join(valid_avatar_styles)}"
            }), 400

        # Get tenant ID from authenticated user
        tenant_id = g.tenant_id

        print(f"[WebsiteRoutes] Generating website for '{lab_name}' (tenant: {tenant_id}, theme: {theme}, avatars: {avatar_style})")

        # Get database session
        db = next(get_db())

        try:
            # Create service and generate website
            service = get_website_generator(tenant_id, db)
            result = service.generate_website(
                lab_name=lab_name,
                focus_areas=focus_areas,
                theme=theme,
                avatar_style=avatar_style
            )
        finally:
            db.close()

        if not result.success:
            return jsonify({
                "success": False,
                "error": result.error or "Website generation failed"
            }), 500

        print(f"[WebsiteRoutes] Generated website: {result.website_id} in {result.generation_time_ms}ms")

        # Save tenant metadata for isolation
        try:
            websites_dir = get_websites_dir()
            meta_path = websites_dir / result.website_id / "metadata.json"
            meta_path.parent.mkdir(parents=True, exist_ok=True)
            with open(meta_path, "w") as mf:
                json.dump({"tenant_id": tenant_id, "lab_name": lab_name, "theme": theme}, mf)
        except Exception:
            pass  # Non-critical

        return jsonify({
            "success": True,
            "website_id": result.website_id,
            "preview_url": result.preview_url,
            "download_url": result.download_url,
            "download_zip_url": f"/api/website/download-zip/{result.website_id}",
            "stats": result.stats,
            "generation_time_ms": result.generation_time_ms,
            "html_length": len(result.html_content) if result.html_content else 0
        })

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] Error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# PREVIEW WEBSITE (Serve the generated HTML)
# ============================================================================

@website_bp.route('/preview/<website_id>', methods=['GET'])
@require_auth
def preview_website(website_id: str):
    """
    Serve the generated website HTML for preview.

    Returns the HTML file directly, can be viewed in browser.
    """
    try:
        if not _validate_website_id(website_id):
            return jsonify({"success": False, "error": "Invalid website ID"}), 400

        websites_dir = get_websites_dir()
        html_path = websites_dir / website_id / "index.html"

        if not html_path.exists():
            return jsonify({
                "success": False,
                "error": "Website not found"
            }), 404

        # Read and return the HTML
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        return Response(html_content, mimetype='text/html')

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] Preview error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DOWNLOAD WEBSITE (Download as HTML file)
# ============================================================================

@website_bp.route('/download/<website_id>', methods=['GET'])
@require_auth
def download_website(website_id: str):
    """
    Download the generated website as an HTML file.
    """
    try:
        if not _validate_website_id(website_id):
            return jsonify({"success": False, "error": "Invalid website ID"}), 400

        websites_dir = get_websites_dir()
        html_path = websites_dir / website_id / "index.html"

        if not html_path.exists():
            return jsonify({
                "success": False,
                "error": "Website not found"
            }), 404

        return send_file(
            html_path,
            mimetype='text/html',
            as_attachment=True,
            download_name=f"{website_id}.html"
        )

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] Download error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DOWNLOAD WEBSITE AS ZIP
# ============================================================================

@website_bp.route('/download-zip/<website_id>', methods=['GET'])
@require_auth
def download_website_zip(website_id: str):
    """
    Download the generated website as a ZIP file.

    The ZIP contains all website files (HTML, CSS, JS, images).
    Ready to deploy to any static hosting service.
    """
    try:
        if not _validate_website_id(website_id):
            return jsonify({"success": False, "error": "Invalid website ID"}), 400

        websites_dir = get_websites_dir()
        website_dir = websites_dir / website_id

        if not website_dir.exists():
            return jsonify({
                "success": False,
                "error": "Website not found"
            }), 404

        # Create ZIP in memory
        from database.models import get_db
        db = next(get_db())
        try:
            # Use service to create ZIP
            service = get_website_generator("", db)  # tenant_id not needed for ZIP
            zip_buffer = service.create_zip(website_id)
        finally:
            db.close()

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f"{website_id}.zip"
        )

    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "Website not found"
        }), 404
    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] ZIP download error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# LIST GENERATED WEBSITES
# ============================================================================

@website_bp.route('/list', methods=['GET'])
@require_auth
def list_websites():
    """
    List generated websites for the current tenant.
    """
    try:
        tenant_id = g.tenant_id
        websites_dir = get_websites_dir()
        websites = []

        for website_dir in sorted(websites_dir.iterdir(), reverse=True):
            if website_dir.is_dir():
                html_path = website_dir / "index.html"
                if html_path.exists():
                    # Filter by tenant
                    meta_path = website_dir / "metadata.json"
                    if meta_path.exists():
                        try:
                            with open(meta_path, "r") as mf:
                                meta = json.load(mf)
                            if meta.get("tenant_id") != tenant_id:
                                continue
                        except Exception:
                            continue
                    websites.append({
                        "website_id": website_dir.name,
                        "preview_url": f"/api/website/preview/{website_dir.name}",
                        "download_url": f"/api/website/download/{website_dir.name}",
                        "created_at": website_dir.stat().st_mtime
                    })

        return jsonify({
            "success": True,
            "websites": websites[:20]  # Limit to 20 most recent
        })

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] List error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# EXTRACT LAB INFO (Preview what will be extracted)
# ============================================================================

@website_bp.route('/extract', methods=['POST'])
@require_auth
def extract_lab_info():
    """
    Extract lab information from knowledge base without generating website.

    Useful for previewing what information will be included in the website.

    Request body:
    {
        "lab_name": "Smith Lab" (required),
        "focus_areas": ["Machine Learning", "NLP"] (optional)
    }

    Response:
    {
        "success": true,
        "lab_info": {
            "name": "Smith Lab",
            "description": "...",
            "research_areas": [...],
            "team_members": [...],
            "publications": [...],
            ...
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        lab_name = data.get('lab_name')
        if not lab_name:
            return jsonify({
                "success": False,
                "error": "lab_name is required"
            }), 400

        focus_areas = data.get('focus_areas', [])
        tenant_id = g.tenant_id

        print(f"[WebsiteRoutes] Extracting lab info for '{lab_name}' (tenant: {tenant_id})")

        # Get database session
        db = next(get_db())

        try:
            service = get_website_generator(tenant_id, db)
            lab_info = service.extract_lab_info(
                lab_name=lab_name,
                focus_areas=focus_areas
            )
        finally:
            db.close()

        # Convert dataclass to dict for JSON response
        lab_info_dict = {
            "name": lab_info.name,
            "description": lab_info.description,
            "research_areas": lab_info.research_areas,
            "team_members": lab_info.team_members,
            "publications": lab_info.publications,
            "projects": lab_info.projects,
            "contact_info": lab_info.contact_info,
            "news_updates": lab_info.news_updates,
            "funding_sources": lab_info.funding_sources,
            "collaborators": lab_info.collaborators
        }

        return jsonify({
            "success": True,
            "lab_info": lab_info_dict
        })

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] Extract error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DELETE WEBSITE
# ============================================================================

@website_bp.route('/delete/<website_id>', methods=['DELETE'])
@require_auth
def delete_website(website_id: str):
    """
    Delete a generated website.
    """
    try:
        if not _validate_website_id(website_id):
            return jsonify({"success": False, "error": "Invalid website ID"}), 400

        import shutil
        websites_dir = get_websites_dir()
        website_path = websites_dir / website_id

        if not website_path.exists():
            return jsonify({
                "success": False,
                "error": "Website not found"
            }), 404

        shutil.rmtree(website_path)

        return jsonify({
            "success": True,
            "message": f"Website {website_id} deleted"
        })

    except Exception as e:
        import traceback
        print(f"[WebsiteRoutes] Delete error: {e}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
