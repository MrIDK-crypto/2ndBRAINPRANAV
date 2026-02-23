"""
Inventory API Routes
Handles CRUD for inventory items, categories, locations, and vendors
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta, timezone
from database.models import (
    SessionLocal, InventoryItem, InventoryCategory,
    InventoryLocation, InventoryVendor, InventoryTransaction,
    InventoryBatch, InventoryCheckout, InventoryAlert, User, utc_now
)
from services.auth_service import require_auth
from services.embedding_service import get_embedding_service
from services.email_notification_service import get_email_service

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')


def get_db():
    return SessionLocal()


def log_transaction(db, tenant_id, item_id, user_id, transaction_type,
                   field_changed=None, old_value=None, new_value=None,
                   quantity_change=None, quantity_before=None, quantity_after=None,
                   notes=None, reference=None):
    """Helper to log inventory transactions for audit trail"""
    transaction = InventoryTransaction(
        tenant_id=tenant_id,
        item_id=item_id,
        user_id=user_id,
        transaction_type=transaction_type,
        field_changed=field_changed,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        quantity_change=quantity_change,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        notes=notes,
        reference=reference
    )
    db.add(transaction)
    return transaction


# ============================================================================
# ITEMS
# ============================================================================

@inventory_bp.route('/items', methods=['GET'])
@require_auth
def list_items():
    """List all inventory items for the tenant with optional filters"""
    db = get_db()
    try:
        query = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        )

        # Apply filters
        category_id = request.args.get('category_id')
        if category_id:
            query = query.filter(InventoryItem.category_id == category_id)

        location_id = request.args.get('location_id')
        if location_id:
            query = query.filter(InventoryItem.location_id == location_id)

        vendor_id = request.args.get('vendor_id')
        if vendor_id:
            query = query.filter(InventoryItem.vendor_id == vendor_id)

        low_stock = request.args.get('low_stock')
        if low_stock == 'true':
            query = query.filter(InventoryItem.quantity <= InventoryItem.min_quantity)

        # Search by name
        search = request.args.get('search')
        if search:
            query = query.filter(InventoryItem.name.ilike(f'%{search}%'))

        # Sort
        sort_by = request.args.get('sort_by', 'name')
        sort_order = request.args.get('sort_order', 'asc')

        if sort_by == 'name':
            query = query.order_by(InventoryItem.name.asc() if sort_order == 'asc' else InventoryItem.name.desc())
        elif sort_by == 'quantity':
            query = query.order_by(InventoryItem.quantity.asc() if sort_order == 'asc' else InventoryItem.quantity.desc())
        elif sort_by == 'warranty_expiry':
            query = query.order_by(InventoryItem.warranty_expiry.asc() if sort_order == 'asc' else InventoryItem.warranty_expiry.desc())
        elif sort_by == 'created_at':
            query = query.order_by(InventoryItem.created_at.asc() if sort_order == 'asc' else InventoryItem.created_at.desc())

        items = query.all()
        return jsonify([item.to_dict() for item in items])
    finally:
        db.close()


@inventory_bp.route('/items', methods=['POST'])
@require_auth
def create_item():
    """Create a new inventory item"""
    db = get_db()
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        if not data.get('name'):
            return jsonify({"error": "Name is required"}), 400

        item = InventoryItem(
            tenant_id=g.tenant_id,
            name=data['name'],
            description=data.get('description'),
            sku=data.get('sku'),
            barcode=data.get('barcode'),
            quantity=data.get('quantity', 0),
            min_quantity=data.get('min_quantity', 0),
            unit=data.get('unit', 'units'),
            unit_price=data.get('unit_price'),
            currency=data.get('currency', 'USD'),
            category_id=data.get('category_id'),
            location_id=data.get('location_id'),
            vendor_id=data.get('vendor_id'),
            purchase_date=datetime.fromisoformat(data['purchase_date'].replace('Z', '+00:00')) if data.get('purchase_date') else None,
            purchase_price=data.get('purchase_price'),
            purchase_order_number=data.get('purchase_order_number'),
            warranty_expiry=datetime.fromisoformat(data['warranty_expiry'].replace('Z', '+00:00')) if data.get('warranty_expiry') else None,
            warranty_notes=data.get('warranty_notes'),
            serial_number=data.get('serial_number'),
            model_number=data.get('model_number'),
            manufacturer=data.get('manufacturer'),
            notes=data.get('notes'),
            image_url=data.get('image_url'),
            created_by=g.user.id if hasattr(g, 'user') and g.user else None
        )

        db.add(item)
        db.commit()
        db.refresh(item)

        # Embed item to Pinecone for RAG search
        try:
            embedding_service = get_embedding_service()
            embedding_service.embed_single_inventory_item(item, g.tenant_id, db)
        except Exception as embed_err:
            print(f"[Inventory] Warning: Failed to embed item: {embed_err}")

        return jsonify(item.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/items/<item_id>', methods=['GET'])
@require_auth
def get_item(item_id):
    """Get a single inventory item"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id
        ).first()

        if not item:
            return jsonify({"error": "Item not found"}), 404

        return jsonify(item.to_dict())
    finally:
        db.close()


@inventory_bp.route('/items/<item_id>', methods=['PUT'])
@require_auth
def update_item(item_id):
    """Update an inventory item"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id
        ).first()

        if not item:
            return jsonify({"error": "Item not found"}), 404

        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON"}), 400

        # Update fields
        updatable_fields = [
            'name', 'description', 'sku', 'barcode', 'quantity', 'min_quantity',
            'unit', 'unit_price', 'currency', 'category_id', 'location_id',
            'vendor_id', 'purchase_price', 'purchase_order_number',
            'warranty_notes', 'serial_number', 'model_number', 'manufacturer',
            'notes', 'image_url', 'is_active'
        ]

        for field in updatable_fields:
            if field in data:
                setattr(item, field, data[field])

        # Handle date fields
        if 'purchase_date' in data:
            item.purchase_date = datetime.fromisoformat(data['purchase_date'].replace('Z', '+00:00')) if data['purchase_date'] else None
        if 'warranty_expiry' in data:
            item.warranty_expiry = datetime.fromisoformat(data['warranty_expiry'].replace('Z', '+00:00')) if data['warranty_expiry'] else None

        item.updated_at = utc_now()
        db.commit()
        db.refresh(item)

        # Re-embed item to Pinecone (update)
        try:
            embedding_service = get_embedding_service()
            embedding_service.embed_single_inventory_item(item, g.tenant_id, db)
        except Exception as embed_err:
            print(f"[Inventory] Warning: Failed to re-embed item: {embed_err}")

        return jsonify(item.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/items/<item_id>', methods=['DELETE'])
@require_auth
def delete_item(item_id):
    """Delete (soft) an inventory item"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id
        ).first()

        if not item:
            return jsonify({"error": "Item not found"}), 404

        # Soft delete
        item.is_active = False
        item.updated_at = utc_now()
        db.commit()

        # Remove from Pinecone
        try:
            embedding_service = get_embedding_service()
            embedding_service.delete_inventory_embeddings([item_id], g.tenant_id)
        except Exception as embed_err:
            print(f"[Inventory] Warning: Failed to delete embedding: {embed_err}")

        return jsonify({"message": "Item deleted successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/items/<item_id>/adjust-quantity', methods=['POST'])
@require_auth
def adjust_quantity(item_id):
    """Adjust item quantity (add or remove stock)"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id
        ).first()

        if not item:
            return jsonify({"error": "Item not found"}), 404

        data = request.get_json()
        adjustment = data.get('adjustment', 0)

        new_quantity = item.quantity + adjustment
        if new_quantity < 0:
            return jsonify({"error": "Quantity cannot be negative"}), 400

        item.quantity = new_quantity
        item.updated_at = utc_now()
        db.commit()
        db.refresh(item)

        return jsonify(item.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# CATEGORIES
# ============================================================================

@inventory_bp.route('/categories', methods=['GET'])
@require_auth
def list_categories():
    """List all inventory categories"""
    db = get_db()
    try:
        categories = db.query(InventoryCategory).filter(
            InventoryCategory.tenant_id == g.tenant_id
        ).order_by(InventoryCategory.name).all()

        return jsonify([cat.to_dict() for cat in categories])
    finally:
        db.close()


@inventory_bp.route('/categories', methods=['POST'])
@require_auth
def create_category():
    """Create a new category"""
    db = get_db()
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({"error": "Name is required"}), 400

        # Check for duplicate
        existing = db.query(InventoryCategory).filter(
            InventoryCategory.tenant_id == g.tenant_id,
            InventoryCategory.name == data['name']
        ).first()

        if existing:
            return jsonify({"error": "Category with this name already exists"}), 409

        category = InventoryCategory(
            tenant_id=g.tenant_id,
            name=data['name'],
            description=data.get('description'),
            color=data.get('color', '#C9A598')
        )

        db.add(category)
        db.commit()
        db.refresh(category)

        return jsonify(category.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/categories/<category_id>', methods=['PUT'])
@require_auth
def update_category(category_id):
    """Update a category"""
    db = get_db()
    try:
        category = db.query(InventoryCategory).filter(
            InventoryCategory.tenant_id == g.tenant_id,
            InventoryCategory.id == category_id
        ).first()

        if not category:
            return jsonify({"error": "Category not found"}), 404

        data = request.get_json()
        if data.get('name'):
            category.name = data['name']
        if 'description' in data:
            category.description = data['description']
        if data.get('color'):
            category.color = data['color']

        category.updated_at = utc_now()
        db.commit()
        db.refresh(category)

        return jsonify(category.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/categories/<category_id>', methods=['DELETE'])
@require_auth
def delete_category(category_id):
    """Delete a category (only if no items use it)"""
    db = get_db()
    try:
        category = db.query(InventoryCategory).filter(
            InventoryCategory.tenant_id == g.tenant_id,
            InventoryCategory.id == category_id
        ).first()

        if not category:
            return jsonify({"error": "Category not found"}), 404

        # Check if any items use this category
        item_count = db.query(InventoryItem).filter(
            InventoryItem.category_id == category_id,
            InventoryItem.is_active == True
        ).count()

        if item_count > 0:
            return jsonify({"error": f"Cannot delete category with {item_count} items"}), 409

        db.delete(category)
        db.commit()

        return jsonify({"message": "Category deleted successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# LOCATIONS
# ============================================================================

@inventory_bp.route('/locations', methods=['GET'])
@require_auth
def list_locations():
    """List all inventory locations"""
    db = get_db()
    try:
        locations = db.query(InventoryLocation).filter(
            InventoryLocation.tenant_id == g.tenant_id
        ).order_by(InventoryLocation.name).all()

        return jsonify([loc.to_dict() for loc in locations])
    finally:
        db.close()


@inventory_bp.route('/locations', methods=['POST'])
@require_auth
def create_location():
    """Create a new location"""
    db = get_db()
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({"error": "Name is required"}), 400

        # Check for duplicate
        existing = db.query(InventoryLocation).filter(
            InventoryLocation.tenant_id == g.tenant_id,
            InventoryLocation.name == data['name']
        ).first()

        if existing:
            return jsonify({"error": "Location with this name already exists"}), 409

        location = InventoryLocation(
            tenant_id=g.tenant_id,
            name=data['name'],
            description=data.get('description'),
            building=data.get('building'),
            room=data.get('room')
        )

        db.add(location)
        db.commit()
        db.refresh(location)

        return jsonify(location.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/locations/<location_id>', methods=['PUT'])
@require_auth
def update_location(location_id):
    """Update a location"""
    db = get_db()
    try:
        location = db.query(InventoryLocation).filter(
            InventoryLocation.tenant_id == g.tenant_id,
            InventoryLocation.id == location_id
        ).first()

        if not location:
            return jsonify({"error": "Location not found"}), 404

        data = request.get_json()
        if data.get('name'):
            location.name = data['name']
        if 'description' in data:
            location.description = data['description']
        if 'building' in data:
            location.building = data['building']
        if 'room' in data:
            location.room = data['room']

        location.updated_at = utc_now()
        db.commit()
        db.refresh(location)

        return jsonify(location.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/locations/<location_id>', methods=['DELETE'])
@require_auth
def delete_location(location_id):
    """Delete a location (only if no items use it)"""
    db = get_db()
    try:
        location = db.query(InventoryLocation).filter(
            InventoryLocation.tenant_id == g.tenant_id,
            InventoryLocation.id == location_id
        ).first()

        if not location:
            return jsonify({"error": "Location not found"}), 404

        # Check if any items use this location
        item_count = db.query(InventoryItem).filter(
            InventoryItem.location_id == location_id,
            InventoryItem.is_active == True
        ).count()

        if item_count > 0:
            return jsonify({"error": f"Cannot delete location with {item_count} items"}), 409

        db.delete(location)
        db.commit()

        return jsonify({"message": "Location deleted successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# VENDORS
# ============================================================================

@inventory_bp.route('/vendors', methods=['GET'])
@require_auth
def list_vendors():
    """List all inventory vendors"""
    db = get_db()
    try:
        vendors = db.query(InventoryVendor).filter(
            InventoryVendor.tenant_id == g.tenant_id
        ).order_by(InventoryVendor.name).all()

        return jsonify([v.to_dict() for v in vendors])
    finally:
        db.close()


@inventory_bp.route('/vendors', methods=['POST'])
@require_auth
def create_vendor():
    """Create a new vendor"""
    db = get_db()
    try:
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({"error": "Name is required"}), 400

        # Check for duplicate
        existing = db.query(InventoryVendor).filter(
            InventoryVendor.tenant_id == g.tenant_id,
            InventoryVendor.name == data['name']
        ).first()

        if existing:
            return jsonify({"error": "Vendor with this name already exists"}), 409

        vendor = InventoryVendor(
            tenant_id=g.tenant_id,
            name=data['name'],
            contact_name=data.get('contact_name'),
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone'),
            website=data.get('website'),
            address=data.get('address'),
            notes=data.get('notes')
        )

        db.add(vendor)
        db.commit()
        db.refresh(vendor)

        return jsonify(vendor.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/vendors/<vendor_id>', methods=['PUT'])
@require_auth
def update_vendor(vendor_id):
    """Update a vendor"""
    db = get_db()
    try:
        vendor = db.query(InventoryVendor).filter(
            InventoryVendor.tenant_id == g.tenant_id,
            InventoryVendor.id == vendor_id
        ).first()

        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404

        data = request.get_json()
        updatable = ['name', 'contact_name', 'contact_email', 'contact_phone',
                     'website', 'address', 'notes']

        for field in updatable:
            if field in data:
                setattr(vendor, field, data[field])

        vendor.updated_at = utc_now()
        db.commit()
        db.refresh(vendor)

        return jsonify(vendor.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/vendors/<vendor_id>', methods=['DELETE'])
@require_auth
def delete_vendor(vendor_id):
    """Delete a vendor (only if no items use it)"""
    db = get_db()
    try:
        vendor = db.query(InventoryVendor).filter(
            InventoryVendor.tenant_id == g.tenant_id,
            InventoryVendor.id == vendor_id
        ).first()

        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404

        # Check if any items use this vendor
        item_count = db.query(InventoryItem).filter(
            InventoryItem.vendor_id == vendor_id,
            InventoryItem.is_active == True
        ).count()

        if item_count > 0:
            return jsonify({"error": f"Cannot delete vendor with {item_count} items"}), 409

        db.delete(vendor)
        db.commit()

        return jsonify({"message": "Vendor deleted successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# ALERTS & STATISTICS
# ============================================================================

@inventory_bp.route('/alerts', methods=['GET'])
@require_auth
def get_alerts():
    """Get inventory alerts (low stock + expiring warranties)"""
    db = get_db()
    try:
        # Low stock items
        low_stock_items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True,
            InventoryItem.quantity <= InventoryItem.min_quantity
        ).all()

        # Items with warranty expiring in next 30 days
        thirty_days = utc_now() + timedelta(days=30)
        expiring_warranty = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True,
            InventoryItem.warranty_expiry != None,
            InventoryItem.warranty_expiry <= thirty_days,
            InventoryItem.warranty_expiry >= utc_now()
        ).all()

        # Items with expired warranty
        expired_warranty = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True,
            InventoryItem.warranty_expiry != None,
            InventoryItem.warranty_expiry < utc_now()
        ).all()

        return jsonify({
            "low_stock": [item.to_dict(include_relations=False) for item in low_stock_items],
            "expiring_warranty": [item.to_dict(include_relations=False) for item in expiring_warranty],
            "expired_warranty": [item.to_dict(include_relations=False) for item in expired_warranty],
            "counts": {
                "low_stock": len(low_stock_items),
                "expiring_warranty": len(expiring_warranty),
                "expired_warranty": len(expired_warranty),
                "total_alerts": len(low_stock_items) + len(expiring_warranty) + len(expired_warranty)
            }
        })
    finally:
        db.close()


@inventory_bp.route('/stats', methods=['GET'])
@require_auth
def get_stats():
    """Get inventory statistics"""
    db = get_db()
    try:
        # Total items
        total_items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).count()

        # Total value
        from sqlalchemy import func
        total_value_result = db.query(
            func.sum(InventoryItem.quantity * InventoryItem.unit_price)
        ).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True,
            InventoryItem.unit_price != None
        ).scalar()
        total_value = float(total_value_result) if total_value_result else 0

        # Items by category
        category_counts = db.query(
            InventoryCategory.name,
            func.count(InventoryItem.id)
        ).outerjoin(
            InventoryItem,
            (InventoryItem.category_id == InventoryCategory.id) &
            (InventoryItem.is_active == True)
        ).filter(
            InventoryCategory.tenant_id == g.tenant_id
        ).group_by(InventoryCategory.name).all()

        # Items by location
        location_counts = db.query(
            InventoryLocation.name,
            func.count(InventoryItem.id)
        ).outerjoin(
            InventoryItem,
            (InventoryItem.location_id == InventoryLocation.id) &
            (InventoryItem.is_active == True)
        ).filter(
            InventoryLocation.tenant_id == g.tenant_id
        ).group_by(InventoryLocation.name).all()

        # Low stock count
        low_stock_count = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True,
            InventoryItem.quantity <= InventoryItem.min_quantity
        ).count()

        # Categories, locations, vendors count
        categories_count = db.query(InventoryCategory).filter(
            InventoryCategory.tenant_id == g.tenant_id
        ).count()

        locations_count = db.query(InventoryLocation).filter(
            InventoryLocation.tenant_id == g.tenant_id
        ).count()

        vendors_count = db.query(InventoryVendor).filter(
            InventoryVendor.tenant_id == g.tenant_id
        ).count()

        return jsonify({
            "total_items": total_items,
            "total_value": total_value,
            "low_stock_count": low_stock_count,
            "categories_count": categories_count,
            "locations_count": locations_count,
            "vendors_count": vendors_count,
            "items_by_category": {name: count for name, count in category_counts},
            "items_by_location": {name: count for name, count in location_counts}
        })
    finally:
        db.close()


@inventory_bp.route('/export', methods=['GET'])
@require_auth
def export_inventory():
    """Export inventory as CSV"""
    db = get_db()
    try:
        items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).all()

        # Build CSV
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Name', 'SKU', 'Quantity', 'Unit', 'Min Quantity', 'Unit Price',
            'Category', 'Location', 'Vendor', 'Manufacturer', 'Model',
            'Serial Number', 'Warranty Expiry', 'Purchase Date', 'Notes'
        ])

        # Data
        for item in items:
            writer.writerow([
                item.name,
                item.sku or '',
                item.quantity,
                item.unit,
                item.min_quantity,
                item.unit_price or '',
                item.category.name if item.category else '',
                item.location.name if item.location else '',
                item.vendor.name if item.vendor else '',
                item.manufacturer or '',
                item.model_number or '',
                item.serial_number or '',
                item.warranty_expiry.strftime('%Y-%m-%d') if item.warranty_expiry else '',
                item.purchase_date.strftime('%Y-%m-%d') if item.purchase_date else '',
                item.notes or ''
            ])

        output.seek(0)

        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=inventory_export.csv'}
        )
    finally:
        db.close()


@inventory_bp.route('/import', methods=['POST'])
@require_auth
def import_inventory():
    """Import inventory from CSV or Excel file"""
    db = get_db()
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        filename = file.filename.lower()

        # Read the file based on type
        import io
        import csv

        rows = []
        headers = []

        if filename.endswith('.csv'):
            # Handle CSV
            content = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content))
            headers = reader.fieldnames or []
            rows = list(reader)
        elif filename.endswith(('.xlsx', '.xls')):
            # Handle Excel
            try:
                import pandas as pd
                df = pd.read_excel(file)
                headers = list(df.columns)
                rows = df.to_dict('records')
            except ImportError:
                # Fallback: try openpyxl directly
                try:
                    from openpyxl import load_workbook
                    wb = load_workbook(file)
                    ws = wb.active
                    data = list(ws.values)
                    if data:
                        headers = [str(h).strip() if h else f'col_{i}' for i, h in enumerate(data[0])]
                        rows = [dict(zip(headers, row)) for row in data[1:]]
                except ImportError:
                    return jsonify({"error": "Excel support not available. Please upload a CSV file."}), 400
        else:
            return jsonify({"error": "Unsupported file type. Please upload CSV or Excel (.xlsx, .xls)"}), 400

        if not rows:
            return jsonify({"error": "File is empty or has no data rows"}), 400

        # Map common header variations to our fields
        header_mapping = {
            'name': ['name', 'item name', 'item', 'product', 'product name', 'title'],
            'sku': ['sku', 'part number', 'part #', 'partnumber', 'item number', 'item #', 'code'],
            'quantity': ['quantity', 'qty', 'stock', 'count', 'amount', 'on hand'],
            'min_quantity': ['min quantity', 'min qty', 'minimum', 'reorder point', 'min stock', 'min_quantity'],
            'unit': ['unit', 'units', 'uom', 'unit of measure'],
            'unit_price': ['unit price', 'price', 'cost', 'unit cost', 'unit_price'],
            'category': ['category', 'type', 'group', 'class'],
            'location': ['location', 'storage', 'warehouse', 'room', 'place'],
            'vendor': ['vendor', 'supplier', 'manufacturer', 'brand'],
            'manufacturer': ['manufacturer', 'mfr', 'make', 'brand'],
            'model_number': ['model', 'model number', 'model #', 'model_number'],
            'serial_number': ['serial', 'serial number', 'serial #', 'serial_number', 'sn'],
            'warranty_expiry': ['warranty', 'warranty expiry', 'warranty date', 'warranty_expiry'],
            'purchase_date': ['purchase date', 'purchased', 'date purchased', 'purchase_date', 'acquired'],
            'notes': ['notes', 'description', 'comments', 'remarks']
        }

        def find_column(row, field_names):
            """Find the value for a field using multiple possible header names"""
            for key in row.keys():
                if key and key.lower().strip() in field_names:
                    return row[key]
            return None

        # Get or create categories, locations, vendors
        category_cache = {}
        location_cache = {}
        vendor_cache = {}

        def get_or_create_category(name):
            if not name or str(name).strip() == '':
                return None
            name = str(name).strip()
            if name in category_cache:
                return category_cache[name]
            cat = db.query(InventoryCategory).filter(
                InventoryCategory.tenant_id == g.tenant_id,
                InventoryCategory.name == name
            ).first()
            if not cat:
                cat = InventoryCategory(tenant_id=g.tenant_id, name=name)
                db.add(cat)
                db.flush()
            category_cache[name] = cat.id
            return cat.id

        def get_or_create_location(name):
            if not name or str(name).strip() == '':
                return None
            name = str(name).strip()
            if name in location_cache:
                return location_cache[name]
            loc = db.query(InventoryLocation).filter(
                InventoryLocation.tenant_id == g.tenant_id,
                InventoryLocation.name == name
            ).first()
            if not loc:
                loc = InventoryLocation(tenant_id=g.tenant_id, name=name)
                db.add(loc)
                db.flush()
            location_cache[name] = loc.id
            return loc.id

        def get_or_create_vendor(name):
            if not name or str(name).strip() == '':
                return None
            name = str(name).strip()
            if name in vendor_cache:
                return vendor_cache[name]
            v = db.query(InventoryVendor).filter(
                InventoryVendor.tenant_id == g.tenant_id,
                InventoryVendor.name == name
            ).first()
            if not v:
                v = InventoryVendor(tenant_id=g.tenant_id, name=name)
                db.add(v)
                db.flush()
            vendor_cache[name] = v.id
            return v.id

        def parse_number(val, default=0):
            if val is None or val == '':
                return default
            try:
                return float(str(val).replace(',', '').replace('$', '').strip())
            except:
                return default

        def parse_date(val):
            if val is None or val == '':
                return None
            try:
                from datetime import datetime
                if isinstance(val, datetime):
                    return val
                val_str = str(val).strip()
                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%m-%d-%Y']:
                    try:
                        return datetime.strptime(val_str, fmt)
                    except:
                        continue
                return None
            except:
                return None

        # Import items
        imported_count = 0
        errors = []

        for i, row in enumerate(rows):
            try:
                name = find_column(row, header_mapping['name'])
                if not name or str(name).strip() == '':
                    continue  # Skip rows without a name

                item = InventoryItem(
                    tenant_id=g.tenant_id,
                    name=str(name).strip(),
                    sku=str(find_column(row, header_mapping['sku']) or '').strip() or None,
                    quantity=int(parse_number(find_column(row, header_mapping['quantity']), 0)),
                    min_quantity=int(parse_number(find_column(row, header_mapping['min_quantity']), 0)),
                    unit=str(find_column(row, header_mapping['unit']) or 'units').strip(),
                    unit_price=parse_number(find_column(row, header_mapping['unit_price'])) or None,
                    category_id=get_or_create_category(find_column(row, header_mapping['category'])),
                    location_id=get_or_create_location(find_column(row, header_mapping['location'])),
                    vendor_id=get_or_create_vendor(find_column(row, header_mapping['vendor'])),
                    manufacturer=str(find_column(row, header_mapping['manufacturer']) or '').strip() or None,
                    model_number=str(find_column(row, header_mapping['model_number']) or '').strip() or None,
                    serial_number=str(find_column(row, header_mapping['serial_number']) or '').strip() or None,
                    warranty_expiry=parse_date(find_column(row, header_mapping['warranty_expiry'])),
                    purchase_date=parse_date(find_column(row, header_mapping['purchase_date'])),
                    notes=str(find_column(row, header_mapping['notes']) or '').strip() or None
                )
                db.add(item)
                imported_count += 1
            except Exception as e:
                errors.append(f"Row {i+2}: {str(e)}")

        db.commit()

        return jsonify({
            "message": f"Successfully imported {imported_count} items",
            "imported_count": imported_count,
            "errors": errors[:10] if errors else []  # Return first 10 errors
        })

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/demo-data', methods=['POST'])
@require_auth
def create_demo_data():
    """Create demo/sample inventory data for testing"""
    db = get_db()
    try:
        # Check if demo data already exists
        existing = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id
        ).count()

        if existing > 0:
            return jsonify({"error": "Inventory already has items. Clear existing data first or add items individually."}), 400

        # Create Categories
        categories = [
            InventoryCategory(tenant_id=g.tenant_id, name="Lab Equipment", description="Major lab instruments and equipment", color="#4F46E5"),
            InventoryCategory(tenant_id=g.tenant_id, name="Consumables", description="Single-use lab supplies", color="#10B981"),
            InventoryCategory(tenant_id=g.tenant_id, name="Reagents", description="Chemical reagents and solutions", color="#F59E0B"),
            InventoryCategory(tenant_id=g.tenant_id, name="Safety Equipment", description="PPE and safety gear", color="#EF4444"),
            InventoryCategory(tenant_id=g.tenant_id, name="Office Supplies", description="General office items", color="#8B5CF6"),
        ]
        for cat in categories:
            db.add(cat)
        db.flush()

        # Create Locations
        locations = [
            InventoryLocation(tenant_id=g.tenant_id, name="Main Lab", building="Science Building", room="101"),
            InventoryLocation(tenant_id=g.tenant_id, name="Storage Room A", building="Science Building", room="B12"),
            InventoryLocation(tenant_id=g.tenant_id, name="Cold Room", building="Science Building", room="103", description="-20C storage"),
            InventoryLocation(tenant_id=g.tenant_id, name="Office", building="Admin Building", room="201"),
            InventoryLocation(tenant_id=g.tenant_id, name="Freezer -80C", building="Science Building", room="101", description="Ultra-low temperature storage"),
        ]
        for loc in locations:
            db.add(loc)
        db.flush()

        # Create Vendors
        vendors = [
            InventoryVendor(tenant_id=g.tenant_id, name="Fisher Scientific", contact_email="orders@fisher.com", website="https://fishersci.com"),
            InventoryVendor(tenant_id=g.tenant_id, name="VWR International", contact_email="support@vwr.com", website="https://vwr.com"),
            InventoryVendor(tenant_id=g.tenant_id, name="Sigma-Aldrich", contact_email="orders@sigma.com", website="https://sigmaaldrich.com"),
            InventoryVendor(tenant_id=g.tenant_id, name="Bio-Rad", contact_email="sales@biorad.com", website="https://bio-rad.com"),
            InventoryVendor(tenant_id=g.tenant_id, name="Thermo Fisher", contact_email="orders@thermofisher.com", website="https://thermofisher.com"),
        ]
        for v in vendors:
            db.add(v)
        db.flush()

        # Create Items
        from datetime import datetime, timedelta
        now = datetime.now()

        items = [
            # Lab Equipment
            InventoryItem(
                tenant_id=g.tenant_id, name="Centrifuge 5424R", sku="CENT-001",
                quantity=2, min_quantity=1, unit="units", unit_price=8500.00,
                category_id=categories[0].id, location_id=locations[0].id, vendor_id=vendors[4].id,
                manufacturer="Eppendorf", model_number="5424R", serial_number="EP2024-1234",
                warranty_expiry=now + timedelta(days=365), purchase_date=now - timedelta(days=180),
                notes="Refrigerated centrifuge, 24 x 1.5mL capacity"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="PCR Thermocycler", sku="PCR-001",
                quantity=1, min_quantity=1, unit="units", unit_price=12000.00,
                category_id=categories[0].id, location_id=locations[0].id, vendor_id=vendors[3].id,
                manufacturer="Bio-Rad", model_number="T100", serial_number="BR2023-5678",
                warranty_expiry=now + timedelta(days=180), purchase_date=now - timedelta(days=400),
                notes="96-well thermal cycler"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Micropipette Set (P10, P100, P1000)", sku="PIP-SET",
                quantity=5, min_quantity=3, unit="sets", unit_price=850.00,
                category_id=categories[0].id, location_id=locations[0].id, vendor_id=vendors[0].id,
                manufacturer="Gilson", model_number="Pipetman L",
                notes="Calibrated quarterly"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Microplate Reader", sku="MPR-001",
                quantity=1, min_quantity=1, unit="units", unit_price=25000.00,
                category_id=categories[0].id, location_id=locations[0].id, vendor_id=vendors[3].id,
                manufacturer="Bio-Rad", model_number="iMark", serial_number="BR2022-9012",
                warranty_expiry=now - timedelta(days=30), purchase_date=now - timedelta(days=800),
                notes="Absorbance reader, 96-well"
            ),

            # Consumables - some low stock
            InventoryItem(
                tenant_id=g.tenant_id, name="Microcentrifuge Tubes 1.5mL", sku="MCT-1.5",
                quantity=50, min_quantity=200, unit="boxes", unit_price=45.00,
                category_id=categories[1].id, location_id=locations[1].id, vendor_id=vendors[0].id,
                notes="500 tubes per box - LOW STOCK"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Pipette Tips 200uL", sku="TIP-200",
                quantity=30, min_quantity=50, unit="boxes", unit_price=35.00,
                category_id=categories[1].id, location_id=locations[1].id, vendor_id=vendors[1].id,
                notes="96 tips per box, filtered"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="PCR Plates 96-well", sku="PCR-96",
                quantity=100, min_quantity=25, unit="plates", unit_price=4.50,
                category_id=categories[1].id, location_id=locations[1].id, vendor_id=vendors[3].id,
                notes="Clear, low-profile"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Serological Pipettes 10mL", sku="SER-10",
                quantity=15, min_quantity=20, unit="boxes", unit_price=65.00,
                category_id=categories[1].id, location_id=locations[1].id, vendor_id=vendors[0].id,
                notes="Sterile, individually wrapped"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Nitrile Gloves (Medium)", sku="GLV-M",
                quantity=8, min_quantity=10, unit="boxes", unit_price=18.00,
                category_id=categories[3].id, location_id=locations[1].id, vendor_id=vendors[1].id,
                notes="100 gloves per box, powder-free"
            ),

            # Reagents
            InventoryItem(
                tenant_id=g.tenant_id, name="Taq DNA Polymerase", sku="TAQ-500",
                quantity=5, min_quantity=2, unit="units", unit_price=180.00,
                category_id=categories[2].id, location_id=locations[4].id, vendor_id=vendors[4].id,
                manufacturer="Thermo Fisher", notes="500 units, store at -20C"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="dNTP Mix 10mM", sku="DNTP-10",
                quantity=10, min_quantity=5, unit="vials", unit_price=95.00,
                category_id=categories[2].id, location_id=locations[4].id, vendor_id=vendors[4].id,
                notes="Equal mix of dATP, dCTP, dGTP, dTTP"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="SYBR Green Master Mix", sku="SYBR-MM",
                quantity=3, min_quantity=2, unit="kits", unit_price=450.00,
                category_id=categories[2].id, location_id=locations[4].id, vendor_id=vendors[3].id,
                warranty_expiry=now + timedelta(days=90),
                notes="For qPCR, 500 rxns per kit"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Ethanol 200 Proof", sku="ETOH-200",
                quantity=4, min_quantity=2, unit="liters", unit_price=85.00,
                category_id=categories[2].id, location_id=locations[2].id, vendor_id=vendors[2].id,
                notes="Molecular biology grade"
            ),

            # Safety Equipment
            InventoryItem(
                tenant_id=g.tenant_id, name="Safety Goggles", sku="GOGGLES",
                quantity=12, min_quantity=5, unit="units", unit_price=15.00,
                category_id=categories[3].id, location_id=locations[0].id, vendor_id=vendors[1].id,
                notes="ANSI Z87.1 certified"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Lab Coats (Large)", sku="COAT-L",
                quantity=6, min_quantity=4, unit="units", unit_price=35.00,
                category_id=categories[3].id, location_id=locations[1].id, vendor_id=vendors[1].id,
                notes="Disposable, knee-length"
            ),

            # Office Supplies
            InventoryItem(
                tenant_id=g.tenant_id, name="Lab Notebooks", sku="NOTEBOOK",
                quantity=20, min_quantity=10, unit="units", unit_price=12.00,
                category_id=categories[4].id, location_id=locations[3].id, vendor_id=vendors[1].id,
                notes="100 pages, grid ruled"
            ),
            InventoryItem(
                tenant_id=g.tenant_id, name="Permanent Markers (Black)", sku="MARKER-BK",
                quantity=24, min_quantity=12, unit="units", unit_price=2.50,
                category_id=categories[4].id, location_id=locations[3].id, vendor_id=vendors[1].id,
                notes="Fine tip, solvent resistant"
            ),
        ]

        for item in items:
            db.add(item)

        db.commit()

        # Refresh items to get IDs and relations
        for item in items:
            db.refresh(item)

        # Embed all items to Pinecone for RAG search
        embedded_count = 0
        try:
            embedding_service = get_embedding_service()
            result = embedding_service.embed_inventory_items(items, g.tenant_id, db)
            embedded_count = result.get('embedded', 0)
        except Exception as embed_err:
            print(f"[Inventory] Warning: Failed to embed demo items: {embed_err}")

        return jsonify({
            "message": "Demo data created successfully",
            "categories_created": len(categories),
            "locations_created": len(locations),
            "vendors_created": len(vendors),
            "items_created": len(items),
            "items_embedded": embedded_count
        })

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/embed-all', methods=['POST'])
@require_auth
def embed_all_inventory():
    """Embed all inventory items to Pinecone for RAG search"""
    db = get_db()
    try:
        embedding_service = get_embedding_service()
        result = embedding_service.embed_tenant_inventory(g.tenant_id, db)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/clear-all', methods=['DELETE'])
@require_auth
def clear_all_inventory():
    """Clear all inventory data (items, categories, locations, vendors) - USE WITH CAUTION"""
    db = get_db()
    try:
        # Get all item IDs before deleting
        item_ids = [str(item.id) for item in db.query(InventoryItem).filter(InventoryItem.tenant_id == g.tenant_id).all()]

        # Delete from Pinecone first
        if item_ids:
            try:
                embedding_service = get_embedding_service()
                embedding_service.delete_inventory_embeddings(item_ids, g.tenant_id)
            except Exception as embed_err:
                print(f"[Inventory] Warning: Failed to delete embeddings: {embed_err}")

        # Delete in order to avoid FK constraints
        db.query(InventoryItem).filter(InventoryItem.tenant_id == g.tenant_id).delete()
        db.query(InventoryCategory).filter(InventoryCategory.tenant_id == g.tenant_id).delete()
        db.query(InventoryLocation).filter(InventoryLocation.tenant_id == g.tenant_id).delete()
        db.query(InventoryVendor).filter(InventoryVendor.tenant_id == g.tenant_id).delete()
        db.commit()

        return jsonify({"message": "All inventory data cleared", "items_removed_from_search": len(item_ids)})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# BARCODE LOOKUP
# ============================================================================

@inventory_bp.route('/barcode/<barcode>', methods=['GET'])
@require_auth
def lookup_barcode(barcode):
    """Look up item by barcode for scanner integration"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.barcode == barcode,
            InventoryItem.is_active == True
        ).first()

        if not item:
            # Also try SKU
            item = db.query(InventoryItem).filter(
                InventoryItem.tenant_id == g.tenant_id,
                InventoryItem.sku == barcode,
                InventoryItem.is_active == True
            ).first()

        if not item:
            return jsonify({"error": "Item not found", "barcode": barcode}), 404

        return jsonify(item.to_dict())
    finally:
        db.close()


# ============================================================================
# TRANSACTION HISTORY
# ============================================================================

@inventory_bp.route('/items/<item_id>/transactions', methods=['GET'])
@require_auth
def get_item_transactions(item_id):
    """Get transaction history for an item"""
    db = get_db()
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)

        transactions = db.query(InventoryTransaction).filter(
            InventoryTransaction.tenant_id == g.tenant_id,
            InventoryTransaction.item_id == item_id
        ).order_by(InventoryTransaction.created_at.desc()).offset(offset).limit(limit).all()

        return jsonify([t.to_dict() for t in transactions])
    finally:
        db.close()


@inventory_bp.route('/transactions', methods=['GET'])
@require_auth
def list_all_transactions():
    """List all transactions for the tenant with filters"""
    db = get_db()
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        transaction_type = request.args.get('type')
        item_id = request.args.get('item_id')
        user_id = request.args.get('user_id')
        days = request.args.get('days', type=int)

        query = db.query(InventoryTransaction).filter(
            InventoryTransaction.tenant_id == g.tenant_id
        )

        if transaction_type:
            query = query.filter(InventoryTransaction.transaction_type == transaction_type)
        if item_id:
            query = query.filter(InventoryTransaction.item_id == item_id)
        if user_id:
            query = query.filter(InventoryTransaction.user_id == user_id)
        if days:
            since = utc_now() - timedelta(days=days)
            query = query.filter(InventoryTransaction.created_at >= since)

        total = query.count()
        transactions = query.order_by(InventoryTransaction.created_at.desc()).offset(offset).limit(limit).all()

        return jsonify({
            "transactions": [t.to_dict() for t in transactions],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    finally:
        db.close()


# ============================================================================
# BATCH/LOT TRACKING
# ============================================================================

@inventory_bp.route('/items/<item_id>/batches', methods=['GET'])
@require_auth
def list_item_batches(item_id):
    """List all batches/lots for an item"""
    db = get_db()
    try:
        batches = db.query(InventoryBatch).filter(
            InventoryBatch.tenant_id == g.tenant_id,
            InventoryBatch.item_id == item_id,
            InventoryBatch.is_active == True
        ).order_by(InventoryBatch.expiry_date.asc()).all()

        return jsonify([b.to_dict() for b in batches])
    finally:
        db.close()


@inventory_bp.route('/items/<item_id>/batches', methods=['POST'])
@require_auth
def create_batch(item_id):
    """Create a new batch/lot for an item"""
    db = get_db()
    try:
        # Verify item exists
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id
        ).first()
        if not item:
            return jsonify({"error": "Item not found"}), 404

        data = request.get_json()
        if not data.get('lot_number'):
            return jsonify({"error": "Lot number is required"}), 400

        batch = InventoryBatch(
            tenant_id=g.tenant_id,
            item_id=item_id,
            lot_number=data['lot_number'],
            batch_number=data.get('batch_number'),
            quantity=data.get('quantity', 0),
            initial_quantity=data.get('quantity', 0),
            manufacture_date=datetime.fromisoformat(data['manufacture_date'].replace('Z', '+00:00')) if data.get('manufacture_date') else None,
            expiry_date=datetime.fromisoformat(data['expiry_date'].replace('Z', '+00:00')) if data.get('expiry_date') else None,
            coa_url=data.get('coa_url'),
            coa_notes=data.get('coa_notes')
        )

        db.add(batch)

        # Update item quantity
        old_qty = item.quantity
        item.quantity += batch.quantity
        item.updated_at = utc_now()

        # Log transaction
        log_transaction(db, g.tenant_id, item_id, g.user.id if hasattr(g, 'user') else None,
                       'BATCH_ADDED', quantity_change=batch.quantity,
                       quantity_before=old_qty, quantity_after=item.quantity,
                       notes=f"Added batch {batch.lot_number}")

        db.commit()
        db.refresh(batch)

        return jsonify(batch.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/batches/<batch_id>', methods=['PUT'])
@require_auth
def update_batch(batch_id):
    """Update a batch"""
    db = get_db()
    try:
        batch = db.query(InventoryBatch).filter(
            InventoryBatch.tenant_id == g.tenant_id,
            InventoryBatch.id == batch_id
        ).first()

        if not batch:
            return jsonify({"error": "Batch not found"}), 404

        data = request.get_json()
        if 'quantity' in data:
            batch.quantity = data['quantity']
        if 'expiry_date' in data:
            batch.expiry_date = datetime.fromisoformat(data['expiry_date'].replace('Z', '+00:00')) if data['expiry_date'] else None
        if 'coa_url' in data:
            batch.coa_url = data['coa_url']
        if 'coa_notes' in data:
            batch.coa_notes = data['coa_notes']
        if 'is_expired' in data:
            batch.is_expired = data['is_expired']

        batch.updated_at = utc_now()
        db.commit()
        db.refresh(batch)

        return jsonify(batch.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# CHECKOUT SYSTEM
# ============================================================================

@inventory_bp.route('/items/<item_id>/checkout', methods=['POST'])
@require_auth
def checkout_item(item_id):
    """Check out an item (equipment or consumable)"""
    db = get_db()
    try:
        item = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.id == item_id,
            InventoryItem.is_active == True
        ).first()

        if not item:
            return jsonify({"error": "Item not found"}), 404

        data = request.get_json() or {}
        quantity = data.get('quantity', 1)
        purpose = data.get('purpose')
        expected_return = data.get('expected_return')
        project_reference = data.get('project_reference')

        # For equipment, check if already checked out
        if item.is_checked_out and quantity == 1:
            return jsonify({"error": "Item is already checked out"}), 400

        # For consumables, check quantity
        if item.quantity < quantity:
            return jsonify({"error": f"Insufficient quantity. Available: {item.quantity}"}), 400

        # Create checkout record
        checkout = InventoryCheckout(
            tenant_id=g.tenant_id,
            item_id=item_id,
            user_id=g.user.id if hasattr(g, 'user') else None,
            quantity=quantity,
            purpose=purpose,
            project_reference=project_reference,
            expected_return=datetime.fromisoformat(expected_return.replace('Z', '+00:00')) if expected_return else None,
            condition_out=data.get('condition', 'Good'),
            status='ACTIVE'
        )
        db.add(checkout)

        # Update item
        old_qty = item.quantity
        item.quantity -= quantity
        item.is_checked_out = True
        item.checked_out_by = g.user.id if hasattr(g, 'user') else None
        item.checked_out_at = utc_now()
        item.last_used = utc_now()
        item.use_count = (item.use_count or 0) + 1
        item.updated_at = utc_now()

        # Log transaction
        log_transaction(db, g.tenant_id, item_id, g.user.id if hasattr(g, 'user') else None,
                       'CHECKED_OUT', quantity_change=-quantity,
                       quantity_before=old_qty, quantity_after=item.quantity,
                       notes=purpose, reference=project_reference)

        db.commit()
        db.refresh(checkout)

        return jsonify(checkout.to_dict()), 201
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/checkouts/<checkout_id>/checkin', methods=['POST'])
@require_auth
def checkin_item(checkout_id):
    """Check in a previously checked out item"""
    db = get_db()
    try:
        checkout = db.query(InventoryCheckout).filter(
            InventoryCheckout.tenant_id == g.tenant_id,
            InventoryCheckout.id == checkout_id,
            InventoryCheckout.status == 'ACTIVE'
        ).first()

        if not checkout:
            return jsonify({"error": "Active checkout not found"}), 404

        data = request.get_json() or {}

        # Update checkout
        checkout.checked_in_at = utc_now()
        checkout.status = 'RETURNED'
        checkout.condition_in = data.get('condition', 'Good')
        checkout.condition_notes = data.get('notes')

        # Update item
        item = db.query(InventoryItem).filter(InventoryItem.id == checkout.item_id).first()
        if item:
            old_qty = item.quantity
            item.quantity += checkout.quantity
            item.is_checked_out = False
            item.checked_out_by = None
            item.checked_out_at = None
            item.updated_at = utc_now()

            # Log transaction
            log_transaction(db, g.tenant_id, item.id, g.user.id if hasattr(g, 'user') else None,
                           'CHECKED_IN', quantity_change=checkout.quantity,
                           quantity_before=old_qty, quantity_after=item.quantity,
                           notes=f"Condition: {checkout.condition_in}")

        db.commit()
        db.refresh(checkout)

        return jsonify(checkout.to_dict())
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/checkouts', methods=['GET'])
@require_auth
def list_checkouts():
    """List all checkouts with filters"""
    db = get_db()
    try:
        status = request.args.get('status', 'ACTIVE')
        user_id = request.args.get('user_id')
        item_id = request.args.get('item_id')

        query = db.query(InventoryCheckout).filter(
            InventoryCheckout.tenant_id == g.tenant_id
        )

        if status != 'all':
            query = query.filter(InventoryCheckout.status == status)
        if user_id:
            query = query.filter(InventoryCheckout.user_id == user_id)
        if item_id:
            query = query.filter(InventoryCheckout.item_id == item_id)

        checkouts = query.order_by(InventoryCheckout.checked_out_at.desc()).all()

        # Enrich with item names
        result = []
        for co in checkouts:
            d = co.to_dict()
            item = db.query(InventoryItem).filter(InventoryItem.id == co.item_id).first()
            d['item_name'] = item.name if item else 'Unknown'
            result.append(d)

        return jsonify(result)
    finally:
        db.close()


# ============================================================================
# ANALYTICS
# ============================================================================

@inventory_bp.route('/analytics', methods=['GET'])
@require_auth
def get_analytics():
    """Get inventory analytics and usage stats"""
    db = get_db()
    try:
        days = request.args.get('days', 30, type=int)
        since = utc_now() - timedelta(days=days)

        # Basic counts
        total_items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).count()

        total_value = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).with_entities(
            db.query(InventoryItem).filter(
                InventoryItem.tenant_id == g.tenant_id,
                InventoryItem.is_active == True,
                InventoryItem.unit_price != None
            ).with_entities(
                (InventoryItem.quantity * InventoryItem.unit_price)
            ).scalar_subquery()
        ).scalar() or 0

        # Get all items for value calculation
        items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).all()
        total_value = sum(item.total_value for item in items)

        # Low stock items
        low_stock_items = [i for i in items if i.is_low_stock]

        # Transaction stats
        transactions = db.query(InventoryTransaction).filter(
            InventoryTransaction.tenant_id == g.tenant_id,
            InventoryTransaction.created_at >= since
        ).all()

        # Usage by type
        checkouts = [t for t in transactions if t.transaction_type == 'CHECKED_OUT']
        adjustments = [t for t in transactions if t.transaction_type == 'QUANTITY_ADJUSTED']

        # Calculate burn rate for top items
        burn_rates = {}
        for t in checkouts:
            if t.item_id not in burn_rates:
                burn_rates[t.item_id] = {'total': 0, 'item_name': None}
            burn_rates[t.item_id]['total'] += abs(t.quantity_change or 0)

        # Get item names for burn rates
        for item_id in burn_rates:
            item = db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
            if item:
                burn_rates[item_id]['item_name'] = item.name
                burn_rates[item_id]['daily_rate'] = burn_rates[item_id]['total'] / days

        # Top 5 by usage
        top_usage = sorted(burn_rates.items(), key=lambda x: x[1]['total'], reverse=True)[:5]

        # Calibration/Maintenance due
        calibration_due = [i for i in items if i.is_calibration_due]
        maintenance_due = [i for i in items if i.is_maintenance_due]

        # Active checkouts
        active_checkouts = db.query(InventoryCheckout).filter(
            InventoryCheckout.tenant_id == g.tenant_id,
            InventoryCheckout.status == 'ACTIVE'
        ).count()

        # Expiring batches
        thirty_days = utc_now() + timedelta(days=30)
        expiring_batches = db.query(InventoryBatch).filter(
            InventoryBatch.tenant_id == g.tenant_id,
            InventoryBatch.is_active == True,
            InventoryBatch.expiry_date != None,
            InventoryBatch.expiry_date <= thirty_days
        ).count()

        return jsonify({
            "period_days": days,
            "summary": {
                "total_items": total_items,
                "total_value": round(total_value, 2),
                "low_stock_count": len(low_stock_items),
                "active_checkouts": active_checkouts,
                "calibration_due": len(calibration_due),
                "maintenance_due": len(maintenance_due),
                "expiring_batches": expiring_batches
            },
            "activity": {
                "total_transactions": len(transactions),
                "checkouts": len(checkouts),
                "adjustments": len(adjustments)
            },
            "top_usage": [
                {
                    "item_id": item_id,
                    "item_name": data['item_name'],
                    "total_used": data['total'],
                    "daily_rate": round(data.get('daily_rate', 0), 2)
                }
                for item_id, data in top_usage
            ],
            "alerts": {
                "low_stock": [{"id": i.id, "name": i.name, "quantity": i.quantity, "min_quantity": i.min_quantity} for i in low_stock_items[:5]],
                "calibration_due": [{"id": i.id, "name": i.name, "next_calibration": i.next_calibration.isoformat() if i.next_calibration else None} for i in calibration_due[:5]],
                "maintenance_due": [{"id": i.id, "name": i.name, "next_maintenance": i.next_maintenance.isoformat() if i.next_maintenance else None} for i in maintenance_due[:5]]
            }
        })
    finally:
        db.close()


# ============================================================================
# EMAIL ALERTS
# ============================================================================

@inventory_bp.route('/alerts/send', methods=['POST'])
@require_auth
def send_inventory_alerts():
    """Send email alerts for low stock, calibration due, etc."""
    db = get_db()
    try:
        data = request.get_json() or {}
        recipient_email = data.get('email')

        # Get user email if not specified
        if not recipient_email and hasattr(g, 'user') and g.user:
            recipient_email = g.user.email

        if not recipient_email:
            return jsonify({"error": "No recipient email specified"}), 400

        # Gather all alerts
        alerts = []
        items = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        ).all()

        for item in items:
            if item.is_low_stock:
                alerts.append({
                    'type': 'LOW_STOCK',
                    'item_name': item.name,
                    'message': f"Below minimum threshold ({item.min_quantity} {item.unit})",
                    'current_value': f"{item.quantity} {item.unit}",
                    'severity': 'CRITICAL' if item.quantity == 0 else 'WARNING'
                })
            if item.is_calibration_due:
                alerts.append({
                    'type': 'CALIBRATION_DUE',
                    'item_name': item.name,
                    'message': "Calibration due soon",
                    'current_value': item.next_calibration.strftime('%Y-%m-%d') if item.next_calibration else 'Overdue',
                    'severity': 'WARNING'
                })
            if item.is_maintenance_due:
                alerts.append({
                    'type': 'MAINTENANCE_DUE',
                    'item_name': item.name,
                    'message': "Maintenance due soon",
                    'current_value': item.next_maintenance.strftime('%Y-%m-%d') if item.next_maintenance else 'Overdue',
                    'severity': 'WARNING'
                })

        # Check expiring batches
        thirty_days = utc_now() + timedelta(days=30)
        batches = db.query(InventoryBatch).filter(
            InventoryBatch.tenant_id == g.tenant_id,
            InventoryBatch.is_active == True,
            InventoryBatch.expiry_date != None,
            InventoryBatch.expiry_date <= thirty_days
        ).all()

        for batch in batches:
            item = db.query(InventoryItem).filter(InventoryItem.id == batch.item_id).first()
            alerts.append({
                'type': 'EXPIRING_BATCH',
                'item_name': f"{item.name if item else 'Unknown'} (Lot: {batch.lot_number})",
                'message': "Batch expiring soon",
                'current_value': batch.expiry_date.strftime('%Y-%m-%d') if batch.expiry_date else 'Unknown',
                'severity': 'CRITICAL' if batch.expiry_date and batch.expiry_date < utc_now() else 'WARNING'
            })

        if not alerts:
            return jsonify({"message": "No alerts to send", "alert_count": 0})

        # Send email
        email_service = get_email_service()
        success = email_service.send_inventory_alert(
            user_email=recipient_email,
            alerts=alerts,
            tenant_name="Your Lab"
        )

        if success:
            # Log alerts sent
            for alert_data in alerts:
                alert = InventoryAlert(
                    tenant_id=g.tenant_id,
                    alert_type=alert_data['type'],
                    severity=alert_data['severity'],
                    message=f"{alert_data['item_name']}: {alert_data['message']}",
                    current_value=alert_data['current_value'],
                    email_sent=True,
                    email_sent_at=utc_now(),
                    email_recipients=recipient_email
                )
                db.add(alert)
            db.commit()

            return jsonify({
                "message": f"Sent {len(alerts)} alerts to {recipient_email}",
                "alert_count": len(alerts),
                "recipient": recipient_email
            })
        else:
            return jsonify({"error": "Failed to send email", "alert_count": len(alerts)}), 500

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/alerts', methods=['GET'])
@require_auth
def list_alerts():
    """List inventory alerts"""
    db = get_db()
    try:
        is_active = request.args.get('active', 'true').lower() == 'true'
        alert_type = request.args.get('type')
        limit = request.args.get('limit', 50, type=int)

        query = db.query(InventoryAlert).filter(
            InventoryAlert.tenant_id == g.tenant_id
        )

        if is_active:
            query = query.filter(InventoryAlert.is_active == True)
        if alert_type:
            query = query.filter(InventoryAlert.alert_type == alert_type)

        alerts = query.order_by(InventoryAlert.created_at.desc()).limit(limit).all()

        return jsonify([a.to_dict() for a in alerts])
    finally:
        db.close()


@inventory_bp.route('/search', methods=['GET'])
@require_auth
def search_inventory():
    """Advanced inventory search"""
    db = get_db()
    try:
        q = request.args.get('q', '')
        category_id = request.args.get('category_id')
        location_id = request.args.get('location_id')
        vendor_id = request.args.get('vendor_id')
        low_stock = request.args.get('low_stock', 'false').lower() == 'true'
        storage_temp = request.args.get('storage_temp')
        hazard_class = request.args.get('hazard_class')

        query = db.query(InventoryItem).filter(
            InventoryItem.tenant_id == g.tenant_id,
            InventoryItem.is_active == True
        )

        if q:
            search_term = f"%{q}%"
            query = query.filter(
                (InventoryItem.name.ilike(search_term)) |
                (InventoryItem.description.ilike(search_term)) |
                (InventoryItem.sku.ilike(search_term)) |
                (InventoryItem.barcode.ilike(search_term)) |
                (InventoryItem.manufacturer.ilike(search_term)) |
                (InventoryItem.notes.ilike(search_term))
            )

        if category_id:
            query = query.filter(InventoryItem.category_id == category_id)
        if location_id:
            query = query.filter(InventoryItem.location_id == location_id)
        if vendor_id:
            query = query.filter(InventoryItem.vendor_id == vendor_id)
        if storage_temp:
            query = query.filter(InventoryItem.storage_temp == storage_temp)
        if hazard_class:
            query = query.filter(InventoryItem.hazard_class == hazard_class)

        items = query.all()

        if low_stock:
            items = [i for i in items if i.is_low_stock]

        return jsonify([item.to_dict() for item in items])
    finally:
        db.close()
