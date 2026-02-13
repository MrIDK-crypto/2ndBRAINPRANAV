#!/bin/bash
# Email Forwarding Setup Script
# Sets up the .env file and tests the connection

echo "============================================================"
echo "EMAIL FORWARDING SETUP"
echo "============================================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.template .env
    echo "✅ Created .env file"
else
    echo "✅ .env file already exists"
fi

# Check if password is set
if grep -q "^FORWARD_EMAIL_PASSWORD=" .env 2>/dev/null; then
    echo "✅ Email password already configured"
else
    echo ""
    echo "⚠️  EMAIL PASSWORD NOT CONFIGURED"
    echo ""
    echo "To set up email forwarding:"
    echo ""
    echo "1. Go to: https://myaccount.google.com/apppasswords"
    echo "2. Sign in to beatatucla@gmail.com"
    echo "3. Create app password named '2nd Brain'"
    echo "4. Copy the 16-character password"
    echo ""
    echo "Then run:"
    echo "  echo 'FORWARD_EMAIL_PASSWORD=your_password_here' >> .env"
    echo ""
    exit 1
fi

echo ""
echo "============================================================"
echo "TESTING CONNECTION"
echo "============================================================"
echo ""

# Test with simple Python script (no dependencies)
python3 << 'EOF'
import imaplib
import os

# Read .env manually (no dependency on python-dotenv)
email_address = "beatatucla@gmail.com"
email_password = None

try:
    with open('.env', 'r') as f:
        for line in f:
            if line.startswith('FORWARD_EMAIL_PASSWORD='):
                email_password = line.split('=', 1)[1].strip().strip('"\'')
                break
except:
    pass

if not email_password:
    print("❌ FORWARD_EMAIL_PASSWORD not found in .env")
    exit(1)

print(f"📧 Testing connection to {email_address}...")
print(f"   Password length: {len(email_password)} chars")

try:
    # Connect to Gmail
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_address, email_password)
    mail.select("INBOX")

    # Count unread emails
    status, messages = mail.search(None, "UNSEEN")
    if status == "OK":
        unread_count = len(messages[0].split())
        print(f"✅ Connected successfully!")
        print(f"📬 Unread emails: {unread_count}")

    mail.close()
    mail.logout()

    print("")
    print("=" * 60)
    print("✅ SETUP COMPLETE!")
    print("=" * 60)
    print("")
    print("Next steps:")
    print("1. Start backend: python app_v2.py")
    print("2. Start frontend: cd ../frontend && npm run dev")
    print("3. Open: http://localhost:3000/integrations")

except Exception as e:
    print(f"❌ Connection failed: {str(e)}")
    print("")
    print("Common issues:")
    print("- Wrong password (check you copied it correctly)")
    print("- 2FA not enabled on beatatucla@gmail.com")
    print("- IMAP not enabled in Gmail settings")
    exit(1)
EOF
