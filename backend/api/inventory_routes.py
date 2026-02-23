"""
Inventory API Routes
Handles CRUD for inventory items, categories, locations, and vendors
"""

from flask import Blueprint, request, jsonify, g
from datetime import datetime, timedelta, timezone
from database.models import (
    SessionLocal, InventoryItem, InventoryCategory,
    InventoryLocation, InventoryVendor, utc_now
)
from services.auth_service import require_auth

inventory_bp = Blueprint('inventory', __name__, url_prefix='/api/inventory')


def get_db():
    return SessionLocal()


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

        return jsonify({
            "message": "Demo data created successfully",
            "categories_created": len(categories),
            "locations_created": len(locations),
            "vendors_created": len(vendors),
            "items_created": len(items)
        })

    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()


@inventory_bp.route('/clear-all', methods=['DELETE'])
@require_auth
def clear_all_inventory():
    """Clear all inventory data (items, categories, locations, vendors) - USE WITH CAUTION"""
    db = get_db()
    try:
        # Delete in order to avoid FK constraints
        db.query(InventoryItem).filter(InventoryItem.tenant_id == g.tenant_id).delete()
        db.query(InventoryCategory).filter(InventoryCategory.tenant_id == g.tenant_id).delete()
        db.query(InventoryLocation).filter(InventoryLocation.tenant_id == g.tenant_id).delete()
        db.query(InventoryVendor).filter(InventoryVendor.tenant_id == g.tenant_id).delete()
        db.commit()

        return jsonify({"message": "All inventory data cleared"})
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()
