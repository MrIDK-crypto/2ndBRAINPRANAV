"""
Minimal Flask app - just for email forwarding
"""
import os
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "test_secret_key_12345"

# CORS
CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

# Email forwarding blueprint (simple version, no database)
from api.email_forwarding_simple import email_forwarding_bp
app.register_blueprint(email_forwarding_bp)

@app.route('/api/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/static/<path:filename>')
def serve_static(filename):
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    return send_from_directory(static_dir, filename)

if __name__ == '__main__':
    print("✅ Minimal backend starting...")
    print("✅ Email forwarding enabled")
    app.run(host='0.0.0.0', port=5003, debug=False)
