#!/usr/bin/env python3
"""
Complete Integration Script
Applies all patches to make Knowledge Vault 100% functional
"""

import sys
import re
from pathlib import Path

def apply_integration():
    """Apply all integration patches to app_universal.py"""

    app_file = Path("app_universal.py")

    if not app_file.exists():
        print("❌ app_universal.py not found!")
        return False

    print("📝 Reading app_universal.py...")
    with open(app_file, 'r') as f:
        content = f.read()

    original_content = content

    # Step 1: Update global declaration
    print("✓ Step 1: Updating global declaration...")
    content = content.replace(
        'global search_index, embedding_index, knowledge_gaps, user_spaces, kb_metadata, enhanced_rag, stakeholder_graph, connector_manager',
        'global search_index, embedding_index, knowledge_gaps, user_spaces, kb_metadata, enhanced_rag, stakeholder_graph, connector_manager, document_manager'
    )

    # Step 2: Add document_manager initialization in load_data()
    print("✓ Step 2: Adding document_manager initialization...")
    connector_init = '''    # Initialize Connector Manager
    try:
        from connectors.connector_manager import ConnectorManager
        connector_manager = ConnectorManager(config_dir=DATA_DIR / "connectors")
        print("✓ Connector manager initialized")
    except Exception as e:
        print(f"⚠ Connector manager not loaded: {e}")
        connector_manager = None'''

    document_manager_init = '''    # Initialize Connector Manager
    try:
        from connectors.connector_manager import ConnectorManager
        connector_manager = ConnectorManager(config_dir=DATA_DIR / "connectors")
        print("✓ Connector manager initialized")
    except Exception as e:
        print(f"⚠ Connector manager not loaded: {e}")
        connector_manager = None

    # Initialize Document Manager
    try:
        from document_manager import DocumentManager
        LLAMAPARSE_KEY = os.getenv("LLAMAPARSE_API_KEY", "")
        document_manager = DocumentManager(
            api_key=OPENAI_API_KEY,
            llamaparse_key=LLAMAPARSE_KEY
        )
        print("✓ Document manager initialized")
    except Exception as e:
        print(f"⚠ Document manager not loaded: {e}")
        document_manager = None'''

    content = content.replace(connector_init, document_manager_init)

    # Step 3: Add document management endpoints before Main section
    print("✓ Step 3: Adding document management endpoints...")

    endpoints_code = '''

# ============================================================================
# Document Management Endpoints
# ============================================================================

@app.route('/api/documents/upload', methods=['POST'])
def upload_document():
    """Upload and process a document"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    file = request.files['file']
    user_id = request.form.get('user_id', 'default')

    result = document_manager.upload_file(file, user_id)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@app.route('/api/documents/review')
def get_documents_for_review():
    """Get documents needing user review"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    review_docs = document_manager.get_documents_for_review(user_id)

    return jsonify({
        'success': True,
        'count': len(review_docs),
        'documents': review_docs
    })


@app.route('/api/documents/<doc_id>/decision', methods=['POST'])
def user_document_decision(doc_id):
    """Process user's decision on a document"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    data = request.get_json()
    decision = data.get('decision')  # 'keep' or 'delete'
    user_id = data.get('user_id', 'default')

    if not decision:
        return jsonify({'success': False, 'error': 'Decision required'}), 400

    result = document_manager.user_decision(doc_id, decision, user_id)
    return jsonify(result)


@app.route('/api/documents/ready-for-rag')
def get_documents_ready_for_rag():
    """Get all work documents ready for RAG processing"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    work_docs = document_manager.get_documents_ready_for_rag(user_id)

    return jsonify({
        'success': True,
        'count': len(work_docs),
        'documents': work_docs
    })


@app.route('/api/documents/stats')
def get_document_stats():
    """Get document statistics"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    user_id = request.args.get('user_id', 'default')
    stats = document_manager.get_statistics(user_id)

    return jsonify({
        'success': True,
        'stats': stats
    })


@app.route('/api/documents/categories')
def get_categories():
    """Get available document categories"""
    global document_manager

    if not document_manager:
        return jsonify({'success': False, 'error': 'Document manager not initialized'}), 500

    return jsonify({
        'success': True,
        'categories': document_manager.CATEGORIES
    })


'''

    # Insert before the Main section
    main_section = '''# ============================================================================
# Main
# ============================================================================'''

    if main_section in content:
        content = content.replace(main_section, endpoints_code + main_section)

    # Check if anything changed
    if content == original_content:
        print("⚠️  No changes were made - patches may already be applied")
        return True

    # Backup original file
    backup_file = Path("app_universal.py.backup")
    print(f"💾 Creating backup: {backup_file}")
    with open(backup_file, 'w') as f:
        f.write(original_content)

    # Write updated content
    print("💾 Writing updated app_universal.py...")
    with open(app_file, 'w') as f:
        f.write(content)

    print("\n✅ Integration patches applied successfully!")
    print(f"   Backup saved to: {backup_file}")
    return True


if __name__ == "__main__":
    print("="*70)
    print("KNOWLEDGE VAULT - FULL INTEGRATION SCRIPT")
    print("="*70)
    print()

    if apply_integration():
        print("\n" + "="*70)
        print("✅ INTEGRATION COMPLETE!")
        print("="*70)
        print("\nNext steps:")
        print("1. Run: ./venv_new/bin/python3 process_takeout_images.py")
        print("2. Restart server: pkill -f python3.*app_universal && ./venv_new/bin/python3 app_universal.py")
        print("3. Test upload: curl -X POST http://localhost:5003/api/documents/upload -F 'file=@test.pdf'")
    else:
        print("\n❌ Integration failed")
        sys.exit(1)
