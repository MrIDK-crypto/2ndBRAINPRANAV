"""
Simple Email Forwarding - No Database Required
"""
import os
import json
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from flask import Blueprint, jsonify

email_forwarding_bp = Blueprint('email_forwarding', __name__, url_prefix='/api/email-forwarding')

# File to store emails
EMAILS_FILE = os.path.join(os.path.dirname(__file__), '..', 'fetched_emails.json')

def save_email_to_file(email_data):
    """Save email to JSON file"""
    try:
        # Load existing emails
        if os.path.exists(EMAILS_FILE):
            with open(EMAILS_FILE, 'r') as f:
                emails = json.load(f)
        else:
            emails = []

        # Add new email
        emails.append(email_data)

        # Save back
        with open(EMAILS_FILE, 'w') as f:
            json.dump(emails, f, indent=2)
    except Exception as e:
        print(f"Error saving email: {e}")

@email_forwarding_bp.route('/status-public', methods=['GET'])
def get_status_public():
    """Get email forwarding status"""
    email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
    email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

    return jsonify({
        "success": True,
        "forwarding_address": email_address,
        "configured": bool(email_password),
        "instructions": f"Forward emails to {email_address}"
    })

@email_forwarding_bp.route('/fetch-public', methods=['POST'])
def fetch_emails_public():
    """Fetch forwarded emails via IMAP"""
    try:
        email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "beatatucla@gmail.com")
        email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

        if not email_password:
            return jsonify({
                "success": False,
                "error": "Email password not configured in .env file"
            }), 500

        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, email_password)
        mail.select("inbox")

        # Search for unread emails
        status, messages = mail.search(None, 'UNSEEN')
        email_ids = messages[0].split()

        processed = 0
        total = len(email_ids)
        emails_data = []

        for email_id in email_ids[:10]:  # Process max 10 emails
            try:
                # Fetch email
                status, msg_data = mail.fetch(email_id, '(RFC822)')

                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])

                        # Get subject
                        subject = msg.get("Subject", "")
                        if subject:
                            decoded = decode_header(subject)[0]
                            if isinstance(decoded[0], bytes):
                                subject = decoded[0].decode(decoded[1] or 'utf-8', errors='ignore')
                            else:
                                subject = decoded[0]

                        # Get from
                        from_addr = msg.get("From", "")

                        # Get body
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() == "text/plain":
                                    body = part.get_payload(decode=True).decode(errors='ignore')
                                    break
                        else:
                            body = msg.get_payload(decode=True).decode(errors='ignore')

                        email_info = {
                            "subject": subject,
                            "from": from_addr,
                            "body": body[:500],  # First 500 chars
                            "fetched_at": datetime.now().isoformat()
                        }
                        emails_data.append(email_info)

                        # Save to JSON file
                        save_email_to_file(email_info)

                        # Mark as read
                        mail.store(email_id, '+FLAGS', '\\Seen')
                        processed += 1

            except Exception as e:
                print(f"Error processing email {email_id}: {e}")
                continue

        mail.close()
        mail.logout()

        return jsonify({
            "success": True,
            "processed": processed,
            "total": total,
            "emails": emails_data,
            "message": f"Successfully fetched {processed} emails"
        })

    except imaplib.IMAP4.error as e:
        return jsonify({
            "success": False,
            "error": f"IMAP error: {str(e)}. Check your email password in .env file"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Error: {str(e)}"
        }), 500

@email_forwarding_bp.route('/documents', methods=['GET'])
def get_documents():
    """Get all fetched emails"""
    try:
        if os.path.exists(EMAILS_FILE):
            with open(EMAILS_FILE, 'r') as f:
                emails = json.load(f)
            return jsonify({
                "success": True,
                "total": len(emails),
                "emails": emails
            })
        else:
            return jsonify({
                "success": True,
                "total": 0,
                "emails": []
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
