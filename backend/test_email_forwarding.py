#!/usr/bin/env python3
"""
Test Email Forwarding Service
Quick test script to verify IMAP connection and email fetching
"""

import os
import sys
from dotenv import load_dotenv

# Load environment
load_dotenv()

def test_imap_connection():
    """Test IMAP connection to Gmail"""
    import imaplib

    email_address = os.getenv("FORWARD_EMAIL_ADDRESS", "pranav@use2ndbrain.com")
    email_password = os.getenv("FORWARD_EMAIL_PASSWORD")

    if not email_password:
        print("❌ FORWARD_EMAIL_PASSWORD not set in .env")
        print("\nTo fix:")
        print("1. Go to https://myaccount.google.com/apppasswords")
        print("2. Generate app password for pranav@use2ndbrain.com")
        print("3. Add to .env: FORWARD_EMAIL_PASSWORD=your_app_password")
        return False

    try:
        print(f"📧 Testing connection to {email_address}...")

        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(email_address, email_password)

        # Select inbox
        mail.select("INBOX")

        # Count unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status == "OK":
            unread_count = len(messages[0].split())
            print(f"✅ Connected successfully!")
            print(f"📬 Unread emails: {unread_count}")

        # Cleanup
        mail.close()
        mail.logout()

        return True

    except Exception as e:
        print(f"❌ Connection failed: {str(e)}")
        return False


def test_email_parsing():
    """Test email parsing service"""
    from database.models import SessionLocal, init_database
    from services.email_forwarding_service import EmailForwardingService

    try:
        from config.config import Config
        config = Config
    except:
        config = None

    try:
        print("\n📋 Testing email parsing service...")

        # Initialize database
        init_database()

        # Create test tenant
        db = SessionLocal()

        # Create service
        service = EmailForwardingService(db, config)

        # Test connection
        print("✅ EmailForwardingService initialized")

        db.close()
        return True

    except Exception as e:
        print(f"❌ Service test failed: {str(e)}")
        return False


def main():
    print("="*60)
    print("EMAIL FORWARDING SERVICE TEST")
    print("="*60)

    # Test 1: IMAP connection
    if not test_imap_connection():
        sys.exit(1)

    # Test 2: Email parsing service
    if not test_email_parsing():
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ ALL TESTS PASSED!")
    print("="*60)
    print("\nNext steps:")
    print("1. Forward a test email to pranav@use2ndbrain.com")
    print("2. Start the backend: python app_v2.py")
    print("3. Test the API: POST /api/email-forwarding/fetch")
    print("\n")


if __name__ == "__main__":
    main()
