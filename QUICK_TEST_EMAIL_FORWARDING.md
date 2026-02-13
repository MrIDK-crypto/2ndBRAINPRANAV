# Quick Test Guide - Email Forwarding

## Problem: "Unable to connect to server"

This means the backend is running but missing the email password configuration.

---

## ✅ Step-by-Step Fix

### Step 1: Create Gmail App Password

1. Open browser and go to: https://myaccount.google.com/apppasswords
2. Sign in with **beatatucla@gmail.com**
3. Click "Select app" → Choose "Other (Custom name)"
4. Type: "2nd Brain Email Forwarding"
5. Click "Generate"
6. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)
7. **Important:** Remove the spaces → `abcdefghijklmnop`

### Step 2: Add to Environment File

```bash
cd /Users/badri/2ndBrainFINAL/backend

# Create .env file (if it doesn't exist)
cp .env.template .env

# Add the email password (replace with your actual password)
echo "" >> .env
echo "# Email Forwarding" >> .env
echo "FORWARD_EMAIL_ADDRESS=beatatucla@gmail.com" >> .env
echo "FORWARD_EMAIL_PASSWORD=abcdefghijklmnop" >> .env
```

### Step 3: Restart Backend Server

```bash
# Stop the current server (Ctrl+C in the terminal where it's running)
# Then restart:
cd /Users/badri/2ndBrainFINAL/backend
python app_v2.py
```

You should see:
```
✓ Database initialized
✓ API blueprints registered
...
* Running on http://0.0.0.0:5003
```

### Step 4: Test the Connection

Run this test script:

```bash
cd /Users/badri/2ndBrainFINAL/backend
python test_email_forwarding.py
```

**Expected output:**
```
📧 Testing connection to beatatucla@gmail.com...
✅ Connected successfully!
📬 Unread emails: 2
✅ ALL TESTS PASSED!
```

**If you see errors:**
- ❌ "FORWARD_EMAIL_PASSWORD not set" → App password not in .env
- ❌ "Authentication failed" → Wrong app password or 2FA not enabled
- ❌ "IMAP not enabled" → Enable IMAP in Gmail settings

---

## 🧪 Quick API Test (Without Frontend)

Once backend is running with the correct password:

### 1. Test Status Endpoint

```bash
# This should work without authentication
curl http://localhost:5003/api/email-forwarding/status
```

**Expected response:**
```json
{
  "success": true,
  "forwarding_address": "beatatucla@gmail.com",
  "configured": true,
  "instructions": "..."
}
```

### 2. Test Fetch Endpoint (Needs Login)

First, you need a user account and token:

```bash
# Create a user (if you don't have one)
curl -X POST http://localhost:5003/api/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123",
    "full_name": "Test User",
    "organization_name": "Test Org"
  }'

# Login to get token
curl -X POST http://localhost:5003/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpass123"
  }'
```

Copy the `access_token` from response, then:

```bash
# Replace YOUR_TOKEN with actual token
curl -X POST http://localhost:5003/api/email-forwarding/fetch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

---

## 📧 Send Test Email

Before testing the fetch:

1. From ANY email account, send to: **beatatucla@gmail.com**
   ```
   To: beatatucla@gmail.com
   Subject: Test Email for 2nd Brain
   Body: This is a test to verify email forwarding works!
   ```

2. Wait 10 seconds for email to arrive

3. Run the fetch command above

4. Should see:
   ```json
   {
     "success": true,
     "processed": 1,
     "total": 1,
     "errors": []
   }
   ```

---

## 🌐 Test via Frontend

1. **Start Backend:**
   ```bash
   cd /Users/badri/2ndBrainFINAL/backend
   python app_v2.py
   ```

2. **Start Frontend:**
   ```bash
   cd /Users/badri/2ndBrainFINAL/frontend
   npm run dev
   ```

3. **Open Browser:**
   - Go to: http://localhost:3000
   - Login with your credentials
   - Go to: http://localhost:3000/integrations

4. **Add Email Forwarding Card:**

   Edit `/Users/badri/2ndBrainFINAL/frontend/app/integrations/page.tsx`

   Add this import at the top:
   ```typescript
   import EmailForwardingCard from '@/components/integrations/EmailForwardingCard';
   ```

   Add this component in the grid (around line 100-150):
   ```typescript
   <EmailForwardingCard />
   ```

5. **Refresh page** - You should see the Email Forwarding card!

6. **Click "Fetch New Emails"** - Emails will be imported!

---

## 🔍 Troubleshooting

### Backend won't start

```bash
# Check for errors
cd /Users/badri/2ndBrainFINAL/backend
python app_v2.py

# If you see import errors, install dependencies:
pip install flask flask-cors python-dotenv sqlalchemy bcrypt PyJWT
```

### "Unable to connect to server" in frontend

```bash
# 1. Check backend is running
curl http://localhost:5003/api/health

# 2. Check CORS settings
# Make sure frontend is running on port 3000 or 3006

# 3. Check .env has correct API URL
cd /Users/badri/2ndBrainFINAL/frontend
cat .env.local

# Should have:
NEXT_PUBLIC_API_BASE_URL=http://localhost:5003
```

### Gmail authentication fails

1. **2-Factor Authentication:** beatatucla@gmail.com MUST have 2FA enabled
2. **App Password:** Use app password, not regular password
3. **IMAP Enabled:** Check Gmail settings → Forwarding/IMAP → Enable IMAP

---

## ✅ Success Checklist

- [ ] Created Gmail App Password
- [ ] Added to .env file
- [ ] Backend starts without errors
- [ ] `python test_email_forwarding.py` passes
- [ ] Can curl the status endpoint
- [ ] Sent test email to beatatucla@gmail.com
- [ ] Fetch endpoint returns processed emails
- [ ] Frontend shows Email Forwarding card
- [ ] Clicking "Fetch" button works
- [ ] Emails appear in Documents page

---

## 🆘 Still Having Issues?

Run this diagnostic script:

```bash
cd /Users/badri/2ndBrainFINAL/backend

python << 'EOF'
import os
from dotenv import load_dotenv

load_dotenv()

print("=== Environment Check ===")
print(f"FORWARD_EMAIL_ADDRESS: {os.getenv('FORWARD_EMAIL_ADDRESS', 'NOT SET')}")
print(f"FORWARD_EMAIL_PASSWORD: {'SET' if os.getenv('FORWARD_EMAIL_PASSWORD') else 'NOT SET'}")
print(f"Password length: {len(os.getenv('FORWARD_EMAIL_PASSWORD', ''))} chars")
print("\nIf password is NOT SET or length is 0, fix your .env file!")
EOF
```

If password is NOT SET:
```bash
cd /Users/badri/2ndBrainFINAL/backend
nano .env
# Add these lines:
# FORWARD_EMAIL_ADDRESS=beatatucla@gmail.com
# FORWARD_EMAIL_PASSWORD=your_16_char_password_here
# Save with Ctrl+X, then Y, then Enter
```
