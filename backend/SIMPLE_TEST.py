#!/usr/bin/env python3
"""
Simple test script - no dependencies needed
Tests email forwarding connection
"""

import imaplib
import os
import sys

def read_env_file():
    """Read .env file manually"""
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip().strip('"\'')
    except FileNotFoundError:
        print("❌ .env file not found!")
        print("\nCreate it with:")
        print("  cp .env.template .env")
        sys.exit(1)
    return env_vars

def main():
    print("=" * 60)
    print("EMAIL FORWARDING - SIMPLE TEST")
    print("=" * 60)
    print()

    # Read environment
    env = read_env_file()

    email_address = env.get('FORWARD_EMAIL_ADDRESS', 'pranav@use2ndbrain.com')
    email_password = env.get('FORWARD_EMAIL_PASSWORD')

    print(f"Email: {email_address}")

    if not email_password:
        print("❌ FORWARD_EMAIL_PASSWORD not set in .env")
        print()
        print("To fix:")
        print("1. Go to: https://myaccount.google.com/apppasswords")
        print("2. Create app password for pranav@use2ndbrain.com")
        print("3. Add to .env:")
        print("   echo 'FORWARD_EMAIL_PASSWORD=your_app_password' >> .env")
        sys.exit(1)

    print(f"Password: {'*' * len(email_password)} ({len(email_password)} chars)")
    print()

    # Test connection
    print("📧 Connecting to Gmail IMAP...")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=10)
        print("✓ Connected to imap.gmail.com")

        mail.login(email_address, email_password)
        print("✓ Login successful")

        mail.select("INBOX")
        print("✓ Selected INBOX")

        # Count unread
        status, messages = mail.search(None, "UNSEEN")
        if status == "OK":
            unread_count = len(messages[0].split())
            print(f"✓ Found {unread_count} unread emails")

        mail.close()
        mail.logout()

        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Email forwarding is configured correctly!")
        print()
        print("Next steps:")
        print("1. Start backend: python app_v2.py")
        print("2. Forward a test email to: pranav@use2ndbrain.com")
        print("3. Use API: POST /api/email-forwarding/fetch")
        print()

    except imaplib.IMAP4.error as e:
        print(f"❌ IMAP Error: {e}")
        print()
        print("Common issues:")
        print("- Wrong app password")
        print("- 2FA not enabled on pranav@use2ndbrain.com")
        print("- IMAP not enabled in Gmail settings")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
