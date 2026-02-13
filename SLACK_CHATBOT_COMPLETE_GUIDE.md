# 2nd Brain Slack Integration - Complete Guide

> **One-Click OAuth + In-Slack Chatbot**
>
> Users connect their Slack workspace with a single click, sync all messages, and get an intelligent chatbot that responds directly in Slack channels.

---

## Table of Contents

1. [How It Works](#how-it-works)
2. [What You Get](#what-you-get)
3. [Security Model](#security-model)
4. [Setup Your Slack App (One-Time)](#setup-your-slack-app)
5. [Configure Environment Variables](#configure-environment-variables)
6. [Deploy to Production](#deploy-to-production)
7. [User Experience](#user-experience)
8. [Troubleshooting](#troubleshooting)

---

## How It Works

### The Complete Flow

```
1. User clicks "Connect Slack" in your app
         ↓
2. Redirected to Slack OAuth page
   - Shows permissions requested
   - User clicks "Allow"
         ↓
3. Slack redirects back to your backend
   - Your backend exchanges code for tokens
   - Stores bot token in database
         ↓
4. Background sync starts
   - Pulls all messages from channels
   - Embeds them in vector database
         ↓
5. Bot is now active in Slack
   - Users can @mention bot
   - Users can DM the bot
   - Users can use /ask command
         ↓
6. Bot responds with RAG-powered answers
   - Searches knowledge base
   - Generates AI answer with citations
   - Shows results in beautiful Slack blocks
```

### Why This Is Secure

**The user maintains control:**
- They create the OAuth connection themselves
- They can see exactly what permissions you request
- They can revoke access anytime from Slack settings
- Your app only has the permissions they explicitly approved
- Multi-tenant isolation (each workspace's data is separate)

**You DON'T need:**
- Them to create their own Slack app
- Manual token copying/pasting
- Slack App Directory approval (unless you want public distribution)

---

## What You Get

### ✅ Already Implemented

1. **OAuth Flow**
   - One-click "Sign in with Slack" button
   - Secure token storage (encrypted in database)
   - Multi-workspace support

2. **Message Syncing**
   - Syncs all public channels
   - Syncs private channels (if bot is added)
   - Syncs DMs (optional)
   - Syncs threaded replies
   - Handles user mentions, links, files

3. **In-Slack Chatbot**
   - Responds to @mentions in channels
   - Responds to direct messages
   - Slash command `/ask <question>`
   - Beautiful message formatting (Slack Block Kit)
   - Citation of sources
   - Confidence scores

4. **RAG Integration**
   - Full-text + semantic search
   - Query expansion (handles acronyms)
   - Cross-encoder reranking
   - Hallucination detection
   - Conversation context

---

## Security Model

### What the Bot CAN Do (Read-Only by Default)

```json
{
  "channels:history": "Read messages from public channels",
  "channels:read": "View list of channels",
  "chat:write": "Send messages (for bot responses)",
  "users:read": "View user names",
  "groups:history": "Read private channels (if invited)",
  "app_mentions:read": "Know when bot is @mentioned",
  "im:history": "Read direct messages to bot",
  "im:write": "Respond to direct messages"
}
```

### What the Bot CANNOT Do

- ❌ Delete messages
- ❌ Delete channels
- ❌ Kick users
- ❌ Change workspace settings
- ❌ Delete files
- ❌ Access channels it's not invited to

### Multi-Tenant Isolation

- Each Slack workspace maps to a tenant_id
- Users can ONLY search their own workspace's data
- JWT authentication required for all API calls
- No cross-workspace data leakage

---

## Setup Your Slack App

### Step 1: Create Slack App (5 minutes)

1. Go to https://api.slack.com/apps
2. Click **"Create New App"** → **"From scratch"**
3. Name: `2nd Brain Chatbot` (or whatever you want)
4. Workspace: Select your development workspace
5. Click **"Create App"**

### Step 2: Configure OAuth & Permissions

1. In the Slack App dashboard, go to **"OAuth & Permissions"**

2. **Redirect URLs** - Add this URL:
   ```
   https://your-backend-domain.com/api/integrations/slack/callback
   ```

   Examples:
   - Production: `https://api.2ndbrain.io/api/integrations/slack/callback`
   - Dev: `http://localhost:5003/api/integrations/slack/callback`

3. **Bot Token Scopes** - Add these scopes:

   ```
   channels:history      # Read public channel messages
   channels:read         # List channels
   chat:write           # Send messages as bot
   users:read           # Get user display names
   groups:history       # Read private channels (if invited)
   groups:read          # List private channels
   app_mentions:read    # Know when @mentioned
   im:history           # Read DMs to bot
   im:write             # Respond to DMs
   commands             # Enable slash commands
   ```

4. Click **"Save Changes"**

### Step 3: Enable Event Subscriptions

1. Go to **"Event Subscriptions"** in the sidebar
2. Toggle **"Enable Events"** to ON
3. **Request URL**: Enter your webhook endpoint
   ```
   https://your-backend-domain.com/api/slack/events
   ```

   Slack will send a challenge request to verify the URL. Your backend at `backend/api/slack_bot_routes.py` handles this automatically.

4. **Subscribe to bot events**:
   ```
   app_mention          # Bot is @mentioned
   message.im           # Direct messages to bot
   ```

5. Click **"Save Changes"**

### Step 4: Create Slash Command

1. Go to **"Slash Commands"** in the sidebar
2. Click **"Create New Command"**
3. Fill in:
   ```
   Command: /ask
   Request URL: https://your-backend-domain.com/api/slack/commands/ask
   Short Description: Ask your knowledge base a question
   Usage Hint: What is our pricing model?
   ```
4. Click **"Save"**

### Step 5: Install App to Workspace

1. Go to **"Install App"** in the sidebar
2. Click **"Install to Workspace"**
3. Review permissions and click **"Allow"**
4. You'll see **Bot User OAuth Token** - DON'T copy it manually, your OAuth flow will get it automatically

### Step 6: Copy Credentials

You need three values from the Slack App dashboard:

1. **Client ID** (found in "Basic Information" → "App Credentials")
2. **Client Secret** (found in "Basic Information" → "App Credentials")
3. **Signing Secret** (found in "Basic Information" → "App Credentials")

Keep these safe! You'll add them to your environment variables next.

---

## Configure Environment Variables

### For Local Development

Create/update `.env` file in `backend/` folder:

```bash
# Slack OAuth Credentials (from Slack App dashboard)
SLACK_CLIENT_ID=1234567890.1234567890
SLACK_CLIENT_SECRET=abc123def456xyz789
SLACK_SIGNING_SECRET=abc123def456xyz789abc123def456xyz7

# Slack OAuth Redirect URI
SLACK_REDIRECT_URI=http://localhost:5003/api/integrations/slack/callback

# Optional: Bot token (for testing, not needed in production)
# SLACK_BOT_TOKEN=xoxb-your-bot-token

# Azure OpenAI (required for RAG)
AZURE_OPENAI_API_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_CHAT_DEPLOYMENT=gpt-4o

# Pinecone (required for vector search)
PINECONE_API_KEY=your-key-here
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=2ndbrain-knowledge

# Database
DATABASE_URL=sqlite:///knowledge_vault.db

# JWT Secret
JWT_SECRET_KEY=your-random-secret-key-here
```

### For Production (Render/Heroku/etc.)

Add these environment variables in your hosting dashboard:

| Variable | Example | Where to Get It |
|----------|---------|-----------------|
| `SLACK_CLIENT_ID` | `1234567890.1234567890` | Slack App → Basic Information |
| `SLACK_CLIENT_SECRET` | `abc123...` | Slack App → Basic Information |
| `SLACK_SIGNING_SECRET` | `abc123...` | Slack App → Basic Information |
| `SLACK_REDIRECT_URI` | `https://api.2ndbrain.io/api/integrations/slack/callback` | Your production URL |
| `AZURE_OPENAI_API_KEY` | `sk-...` | Azure Portal |
| `PINECONE_API_KEY` | `...` | Pinecone Dashboard |
| `JWT_SECRET_KEY` | Random string | Generate with `openssl rand -hex 32` |

---

## Deploy to Production

### Render.com Deployment

1. **Update Redirect URL in Slack App**:
   - Go to your Slack App → OAuth & Permissions
   - Add redirect URL: `https://your-app.onrender.com/api/integrations/slack/callback`

2. **Update Event Subscription URL**:
   - Go to Event Subscriptions
   - Update Request URL: `https://your-app.onrender.com/api/slack/events`
   - Update Slash Command URL: `https://your-app.onrender.com/api/slack/commands/ask`

3. **Set Environment Variables in Render**:
   - Go to your Render service → Environment
   - Add all variables from the table above
   - Make sure `SLACK_REDIRECT_URI` matches exactly

4. **Deploy**:
   ```bash
   git add .
   git commit -m "Add Slack chatbot functionality"
   git push origin main
   ```

   Render will auto-deploy.

5. **Test the Webhook**:
   - Go to your Slack App → Event Subscriptions
   - Click "Retry" next to the Request URL
   - Should see "Verified ✓"

---

## User Experience

### For Users Connecting Slack

```
1. User visits your app
2. Goes to Integrations page
3. Clicks "Connect Slack"
         ↓
   Redirected to Slack:
   "2nd Brain Chatbot wants to access:
    - View messages in channels
    - Send messages
    - View user information"
         ↓
4. User clicks "Allow"
5. Redirected back to your app
6. Success! "Slack connected ✓"
7. Sync starts automatically
```

### Using the Chatbot in Slack

**Method 1: @Mention in Channels**
```
User: @2ndBrain What is our pricing model?

2ndBrain:
🔍 Results for: What is our pricing model?
━━━━━━━━━━━━━━━━━━━━━━━━━
Our pricing model is based on a tiered subscription...

📚 Sources:
1. Pricing Document (from box)
2. Sales Email Thread (from gmail)

✅ Confidence: 92% | 🧠 Enhanced RAG | ⚡ Real-time
```

**Method 2: Direct Message**
```
User (DM): How do I onboard a new employee?

2ndBrain: Here's our employee onboarding process...
```

**Method 3: Slash Command**
```
/ask What are the Q4 goals?

(Response visible to everyone in channel)
```

---

## Troubleshooting

### Slack Can't Verify Event URL

**Error:** `Verification Failed: We couldn't reach your URL...`

**Causes:**
1. Backend not deployed/running
2. URL is incorrect
3. Firewall blocking Slack
4. `SLACK_SIGNING_SECRET` not set

**Fix:**
```bash
# Check backend is running
curl https://your-backend.com/api/slack/health

# Should return:
{"status": "healthy", "bot_enabled": true}

# Check logs for:
[SlackBot] WARNING: SLACK_SIGNING_SECRET not set
```

### OAuth Flow Returns "redirect_uri_mismatch"

**Cause:** Redirect URI in Slack app doesn't match `SLACK_REDIRECT_URI` env var

**Fix:**
1. Check Slack App → OAuth & Permissions → Redirect URLs
2. Check your env var: `echo $SLACK_REDIRECT_URI`
3. Must match EXACTLY (including https:// vs http://)

### Bot Not Responding to @Mentions

**Causes:**
1. Event subscription not enabled
2. Bot not in channel
3. Workspace not connected

**Fix:**
```bash
# Check bot is registered for the workspace
# Backend logs should show:
[SlackBot] Registered workspace T123456 -> tenant abc-123

# Invite bot to channel:
In Slack: /invite @2ndBrain

# Check bot can see messages:
curl -X POST https://your-backend.com/api/slack/events \
  -H "Content-Type: application/json" \
  -d '{"type":"url_verification","challenge":"test"}'
```

### "/ask Command Not Found"

**Cause:** Slash command not created or URL wrong

**Fix:**
1. Go to Slack App → Slash Commands
2. Verify `/ask` command exists
3. Verify Request URL matches your backend
4. Reinstall app to workspace

### Bot Responds But Says "No Results"

**Cause:** Knowledge base is empty or not synced

**Fix:**
```bash
# Check if documents are synced
curl https://your-backend.com/api/documents \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Should return documents

# Check if embeddings are generated
# Backend logs should show:
[Pinecone] Upserted 150 vectors for tenant abc-123

# Manually trigger sync:
curl -X POST https://your-backend.com/api/integrations/slack/sync \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### "Invalid Signature" Errors

**Cause:** `SLACK_SIGNING_SECRET` is wrong or missing

**Fix:**
1. Go to Slack App → Basic Information → App Credentials
2. Copy "Signing Secret"
3. Update `SLACK_SIGNING_SECRET` env var
4. Restart backend

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────┐
│  User's Slack Workspace                                      │
│  - #general channel                                          │
│  - #engineering channel                                      │
│  - @2ndBrain bot user                                        │
└─────────────┬────────────────────────────────────────────────┘
              │
              │ (1) OAuth Flow (one-time)
              ├──────────────────────────────────────►
              │       GET /api/integrations/slack/auth
              │       POST /api/integrations/slack/callback
              │
              │ (2) Message Sync (background)
              ├──────────────────────────────────────►
              │       POST /api/integrations/slack/sync
              │
              │ (3) Bot Events (real-time)
              ├──────────────────────────────────────►
              │       POST /api/slack/events
              │       POST /api/slack/commands/ask
              │
┌─────────────▼────────────────────────────────────────────────┐
│  Your 2nd Brain Backend                                      │
│                                                               │
│  ┌─────────────────┐      ┌──────────────────┐             │
│  │ Integration API │─────→│ Slack Connector  │             │
│  │ (OAuth)         │      │ (Message Sync)   │             │
│  └─────────────────┘      └──────────────────┘             │
│                                     │                        │
│  ┌─────────────────┐               │                        │
│  │ Slack Bot API   │               │                        │
│  │ (Webhooks)      │               │                        │
│  └────────┬────────┘               │                        │
│           │                        │                        │
│           │          ┌─────────────▼──────────┐             │
│           └─────────→│ Slack Bot Service      │             │
│                      │ - handle_app_mention() │             │
│                      │ - handle_message()     │             │
│                      │ - handle_ask_command() │             │
│                      └────────────┬───────────┘             │
│                                   │                        │
│                      ┌────────────▼───────────┐             │
│                      │ Enhanced Search        │             │
│                      │ Service (RAG)          │             │
│                      └────────────┬───────────┘             │
│                                   │                        │
│           ┌───────────────────────┴──────────────┐          │
│           │                                       │          │
│  ┌────────▼─────────┐                  ┌─────────▼────────┐ │
│  │ Pinecone         │                  │ Azure OpenAI     │ │
│  │ Vector Store     │                  │ (GPT-4o)         │ │
│  └──────────────────┘                  └──────────────────┘ │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

---

## Files Reference

| File | Purpose |
|------|---------|
| `backend/api/slack_bot_routes.py` | Webhook endpoints (events, commands) |
| `backend/services/slack_bot_service.py` | Bot logic (RAG queries, formatting) |
| `backend/connectors/slack_connector.py` | OAuth + message syncing |
| `backend/api/integration_routes.py` | OAuth flow endpoints |
| `backend/services/enhanced_search_service.py` | RAG search engine |
| `frontend/components/integrations/Integrations.tsx` | UI for connecting Slack |

---

## FAQ

**Q: Do users need to create their own Slack app?**
A: **NO!** You create ONE Slack app. Users just click "Connect" and authorize.

**Q: Do I need Slack App Directory approval?**
A: **NO**, unless you want a public "Add to Slack" button. Private distribution works without approval.

**Q: Can I charge users for this?**
A: **YES!** This is a standard B2B SaaS integration. Users pay you, not Slack.

**Q: What if a user has multiple Slack workspaces?**
A: They can connect multiple workspaces. Each workspace maps to a separate tenant_id in your database.

**Q: Can the bot be customized per workspace?**
A: Yes! You can add per-tenant settings (bot name, greeting message, etc.) in the database.

**Q: How much does this cost to run?**
A:
- Slack API: FREE
- Azure OpenAI: ~$0.01-0.05 per query
- Pinecone: ~$70/month (starter plan)

**Q: Is this secure for enterprise customers?**
A: Yes:
- OAuth 2.0 standard
- Encrypted token storage
- Request signature verification
- Multi-tenant isolation
- No cross-workspace data access

---

## What's Next?

### Enhancements You Can Add

1. **Conversation Memory**: Track conversation history for contextual follow-ups
2. **Interactive Buttons**: Add "Show more sources", "Ask follow-up", etc.
3. **Admin Commands**: `/2ndbrain-settings`, `/2ndbrain-sync`, etc.
4. **Notifications**: Alert users when new knowledge gaps are found
5. **Channel-Specific Bots**: Different bot behavior per channel
6. **User Preferences**: Per-user settings (verbosity, sources shown, etc.)
7. **Analytics**: Track most asked questions, user engagement

### Monetization Ideas

1. **Freemium**: 50 queries/month free, unlimited for $49/month
2. **Per-Seat Pricing**: $10/user/month
3. **Usage-Based**: $0.25 per query
4. **Enterprise**: Custom pricing for 100+ users

---

**You're all set!** 🎉

Users can now connect their Slack workspaces with one click and get an intelligent chatbot that searches your knowledge base in real-time.

For issues or questions, check the troubleshooting section or open an issue on GitHub.
