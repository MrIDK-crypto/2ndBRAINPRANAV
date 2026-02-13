# Email Forwarding Integration Setup

## Overview

This replaces the OAuth Gmail integration with a simpler email forwarding system:
- Users forward emails to `beatatucla@gmail.com`
- System polls the inbox via IMAP
- Emails are parsed and added to the knowledge base
- No OAuth needed - users have full privacy control

---

## Setup Steps

### 1. Create Gmail App Password

Since `beatatucla@gmail.com` has 2-factor authentication, you need an App Password:

1. Go to: https://myaccount.google.com/apppasswords
2. Sign in to beatatucla@gmail.com
3. Click "Select app" → Other (Custom name)
4. Enter: "2nd Brain Email Forwarding"
5. Click "Generate"
6. Copy the 16-character password (e.g., `abcd efgh ijkl mnop`)

### 2. Configure Backend

Add to `/Users/badri/2ndBrainFINAL/backend/.env`:

```bash
# Email Forwarding Integration
FORWARD_EMAIL_ADDRESS=beatatucla@gmail.com
FORWARD_EMAIL_PASSWORD=abcdefghijklmnop  # Paste your app password (remove spaces)
```

### 3. Run the Backend

```bash
cd /Users/badri/2ndBrainFINAL/backend

# Activate virtual environment (if you have one)
source venv/bin/activate  # or source venv312/bin/activate

# Start server
python app_v2.py
```

Backend runs on: **http://localhost:5003**

### 4. Run the Frontend

```bash
cd /Users/badri/2ndBrainFINAL/frontend

# Start Next.js
npm run dev
```

Frontend runs on: **http://localhost:3000**

---

## How to Use

### For Users:

1. Open the Integrations page
2. See the "Email Forwarding" card with instructions
3. Forward any email to `beatatucla@gmail.com`
4. Click "Fetch New Emails" button
5. Emails appear in Documents page for classification

### For Testing:

1. Send a test email to `beatatucla@gmail.com`:
   ```
   To: beatatucla@gmail.com
   Subject: Test Email for 2nd Brain
   Body: This is a test email to verify the forwarding system works.
   ```

2. In the app, click "Fetch New Emails"

3. Check the Documents page - should see the email

---

## API Endpoints

### Get Status
```bash
GET /api/email-forwarding/status
Authorization: Bearer <token>

Response:
{
  "success": true,
  "forwarding_address": "beatatucla@gmail.com",
  "configured": true,
  "instructions": "..."
}
```

### Fetch Emails
```bash
POST /api/email-forwarding/fetch
Authorization: Bearer <token>

Response:
{
  "success": true,
  "processed": 5,
  "total": 5,
  "errors": []
}
```

---

## Architecture

```
User forwards email
    ↓
beatatucla@gmail.com inbox
    ↓
Backend polls via IMAP (when user clicks "Fetch")
    ↓
EmailForwardingService extracts:
  - Subject
  - Original sender (from forwarded email)
  - Body content
  - Timestamp
    ↓
Creates Document in database
    ↓
Document appears in Documents page
    ↓
User classifies as Work/Personal
    ↓
Added to knowledge base & embeddings
```

---

## Files Created/Modified

### Backend:
- ✅ `services/email_forwarding_service.py` - IMAP polling service
- ✅ `api/email_forwarding_routes.py` - API endpoints
- ✅ `app_v2.py` - Registered new blueprint
- ✅ `.env.template` - Added email credentials

### Frontend:
- ✅ `components/integrations/EmailForwardingCard.tsx` - UI component

---

## Security Notes

1. **App Password**: Never commit the app password to Git
2. **Read-Only**: IMAP connection only reads emails (no sending)
3. **User Control**: Users decide what to forward
4. **No OAuth**: No access to user's personal Gmail

---

## Troubleshooting

### "FORWARD_EMAIL_PASSWORD not set"
- Add the app password to backend/.env
- Restart the backend server

### "Failed to connect to IMAP"
- Check the app password is correct
- Ensure beatatucla@gmail.com has IMAP enabled
- Check firewall/network settings

### "No new emails"
- Emails must be **unread** in the inbox
- After processing, emails are marked as read
- Forward another email to test

---

## Next Steps

### Add to Integrations Page:

Edit `/Users/badri/2ndBrainFINAL/frontend/app/integrations/page.tsx`:

```tsx
import EmailForwardingCard from '@/components/integrations/EmailForwardingCard';

// Add in the integrations grid:
<EmailForwardingCard />
```

### Optional Enhancements:

1. **Auto-polling**: Add cron job to check every hour
2. **Webhook**: Use Gmail API push notifications
3. **Per-user forwarding**: Generate unique email per user
4. **Attachment support**: Parse email attachments

---

## Testing Checklist

- [ ] Backend starts without errors
- [ ] GET /api/email-forwarding/status returns configured: true
- [ ] Forward test email to beatatucla@gmail.com
- [ ] POST /api/email-forwarding/fetch processes the email
- [ ] Email appears in Documents page
- [ ] Can classify the email as Work/Personal
- [ ] Email content is searchable via RAG
