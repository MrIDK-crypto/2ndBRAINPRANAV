"""
Grant Finder API Routes
REST endpoints for searching grants and managing lab research profiles.
"""

from flask import Blueprint, request, jsonify, g
from database.models import SessionLocal, Tenant
from services.auth_service import require_auth
from services.grant_finder_service import get_grant_finder

grant_bp = Blueprint('grants', __name__, url_prefix='/api/grants')


def get_db():
    return SessionLocal()


@grant_bp.route('/search', methods=['GET'])
@require_auth
def search_grants():
    """
    Search grants across NIH RePORTER and Grants.gov.

    Query params:
        q: Search query (required)
        agencies: Comma-separated agency codes (NIH, NSF, DOE, DOD)
        activity_codes: Comma-separated (R01, R21, etc.)
        amount_min: Minimum award amount
        amount_max: Maximum award amount
        limit: Max results (default 20, max 50)
    """
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({
                "success": False,
                "error": "Search query 'q' is required"
            }), 400

        agencies_str = request.args.get('agencies', '')
        agencies = [a.strip() for a in agencies_str.split(',') if a.strip()] or None

        codes_str = request.args.get('activity_codes', '')
        activity_codes = [c.strip() for c in codes_str.split(',') if c.strip()] or None

        amount_min = request.args.get('amount_min', type=int)
        amount_max = request.args.get('amount_max', type=int)
        limit = min(request.args.get('limit', 20, type=int), 50)

        tenant_id = getattr(g, 'tenant_id', 'local-tenant')

        # Get lab profile for scoring
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            lab_profile = (tenant.settings or {}).get('grant_profile', {}) if tenant else {}
        finally:
            db.close()

        # Search and score
        finder = get_grant_finder()
        result = finder.search(
            query=query,
            tenant_id=tenant_id,
            lab_profile=lab_profile,
            agencies=agencies,
            activity_codes=activity_codes,
            amount_min=amount_min,
            amount_max=amount_max,
            limit=limit
        )

        return jsonify({
            "success": True,
            **result
        })

    except Exception as e:
        print(f"[GrantSearch] Error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@grant_bp.route('/profile', methods=['GET'])
@require_auth
def get_profile():
    """Get the lab's grant research profile."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return jsonify({"success": False, "error": "Tenant not found"}), 404

            profile = (tenant.settings or {}).get('grant_profile', {})
            return jsonify({
                "success": True,
                "profile": profile
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@grant_bp.route('/profile', methods=['PUT'])
@require_auth
def update_profile():
    """Update the lab's grant research profile."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "Request body required"}), 400

        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if not tenant:
                return jsonify({"success": False, "error": "Tenant not found"}), 404

            settings = tenant.settings or {}
            settings['grant_profile'] = {
                "research_areas": data.get("research_areas", []),
                "keywords": data.get("keywords", []),
                "department": data.get("department", ""),
                "institution": data.get("institution", ""),
                "preferred_agencies": data.get("preferred_agencies", ["NIH", "NSF"]),
                "budget_range": data.get("budget_range", {"min": 50000, "max": 1000000}),
                "activity_codes": data.get("activity_codes", ["R01", "R21"]),
                "auto_generated": False,
                "last_updated": __import__('datetime').datetime.utcnow().isoformat()
            }
            tenant.settings = settings

            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(tenant, 'settings')
            db.commit()

            return jsonify({
                "success": True,
                "profile": settings['grant_profile']
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@grant_bp.route('/auto-profile', methods=['POST'])
@require_auth
def auto_generate_profile():
    """Auto-generate lab profile from ingested documents."""
    try:
        tenant_id = getattr(g, 'tenant_id', 'local-tenant')
        db = get_db()
        try:
            finder = get_grant_finder()
            profile = finder.auto_generate_profile(tenant_id, db)

            # Save to tenant settings
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                settings = tenant.settings or {}
                settings['grant_profile'] = profile
                tenant.settings = settings

                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(tenant, 'settings')
                db.commit()

            return jsonify({
                "success": True,
                "profile": profile
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
