# Slack App Setup Guide
## Complete guide to creating and publishing the 2nd Brain Slack bot

---

## TABLE OF CONTENTS

1. [Create Slack App](#create-slack-app)
2. [Configure OAuth & Permissions](#configure-oauth--permissions)
3. [Configure Slash Commands](#configure-slash-commands)
4. [Configure Event Subscriptions](#configure-event-subscriptions)
5. [Configure Interactive Components](#configure-interactive-components)
6. [Install to Workspace (Testing)](#install-to-workspace-testing)
7. [Submit for Distribution](#submit-for-distribution)
8. [Add "Add to Slack" Button](#add-add-to-slack-button)
9. [Environment Variables](#environment-variables)
10. [Testing](#testing)

---

## 1. CREATE SLACK APP

### Step 1: Go to Slack API Portal

1. Visit https://api.slack.com/apps
2. Click **"Create New App"**
3. Choose **"From scratch"**

### Step 2: Basic Information

Fill in:
- **App Name**: `2nd Brain`
- **Workspace**: Select your development workspace
- Click **"Create App"**

### Step 3: Display Information (App Home)

Navigate to **App Home** → **Edit**:

**App Name**: `2nd Brain`

**Short Description** (150 chars max):
```
AI-powered knowledge assistant. Search your organization's knowledge base directly from Slack.
```

**Long Description**:
```
2nd Brain brings your organization's knowledge base directly into Slack. Ask questions, get AI-powered answers with source citations, and never lose critical knowledge again.

Features:
✅ Ask questions with /ask command
✅ Mention @2ndBrain in any channel
✅ Direct message for private queries
✅ Real-time knowledge search
✅ Source citations for transparency
✅ Enterprise-grade security

Perfect for:
- Knowledge transfer during onboarding
- Answering repeated questions
- Finding documented decisions
- Accessing technical documentation
- Preventing knowledge loss
```

**App Icon** (512x512px):
- Upload your 2nd Brain logo
- Ensure it's clear at small sizes

**Background Color**: `#081028` (your brand color)

---

## 2. CONFIGURE OAUTH & PERMISSIONS

### Step 1: Redirect URLs

Navigate to **OAuth & Permissions** → **Redirect URLs**:

Add:
```
https://your-domain.com/api/slack/oauth/callback
https://app.2ndbrain.io/api/slack/oauth/callback  (production)
http://localhost:5003/api/slack/oauth/callback  (development)
```

### Step 2: Bot Token Scopes

Navigate to **OAuth & Permissions** → **Scopes** → **Bot Token Scopes**:

Add these scopes:

| Scope | Purpose |
|-------|---------|
| `app_mentions:read` | Hear when @2ndBrain is mentioned |
| `channels:history` | Read messages in channels (for context) |
| `channels:read` | View channel list |
| `chat:write` | Post messages as the bot |
| `commands` | Receive slash commands (/ask) |
| `im:history` | Read direct messages to the bot |
| `im:read` | View DM list |
| `im:write` | Send direct messages |
| `users:read` | Get user info for personalization |

**Why we need these**:
- `commands`: For `/ask <question>` slash command
- `app_mentions:read` + `channels:history`: For `@2ndBrain what is...` in channels
- `im:history` + `im:read` + `im:write`: For direct messages to the bot
- `chat:write`: To respond to users
- `users:read`: To personalize responses

### Step 3: Install Bot (for testing)

Scroll up → Click **"Install to Workspace"** → **"Allow"**

Copy the **Bot User OAuth Token** (starts with `xoxb-`). You'll need this.

---

## 3. CONFIGURE SLASH COMMANDS

### Step 1: Create /ask Command

Navigate to **Slash Commands** → **Create New Command**:

**Command**: `/ask`

**Request URL**: `https://your-domain.com/api/slack/commands/ask`

**Short Description**: `Ask 2nd Brain a question`

**Usage Hint**: `What is our pricing model?`

**Escape channels, users, and links**: ✅ (checked)

Click **"Save"**

### Example Usage

Users will type:
```
/ask What is our onboarding process?
/ask How do I set up the development environment?
/ask What are the pricing tiers?
```

---

## 4. CONFIGURE EVENT SUBSCRIPTIONS

### Step 1: Enable Events

Navigate to **Event Subscriptions** → **Enable Events**: ✅

**Request URL**: `https://your-domain.com/api/slack/events`

**Important**: Your endpoint must:
1. Respond within 3 seconds
2. Return `200 OK`
3. Handle the `url_verification` challenge

### Step 2: Subscribe to Bot Events

Under **Subscribe to bot events**, add:

| Event | Purpose |
|-------|---------|
| `app_mention` | When @2ndBrain is mentioned |
| `message.im` | Direct messages to the bot |

Click **"Save Changes"**

### How It Works

**Channel Mention**:
```
User: @2ndBrain What is our vacation policy?
Bot: [Searches knowledge base and replies in thread]
```

**Direct Message**:
```
User: What's the password for the staging server?
Bot: [Searches knowledge base and replies privately]
```

---

## 5. CONFIGURE INTERACTIVE COMPONENTS

### Step 1: Enable Interactivity

Navigate to **Interactivity & Shortcuts** → **Interactivity**: ✅

**Request URL**: `https://your-domain.com/api/slack/interactive`

### Step 2: (Optional) Add Shortcuts

**Future enhancement**: Add global shortcuts like:
- "Search Knowledge Base"
- "Ask 2nd Brain"

Click **"Save Changes"**

---

## 6. INSTALL TO WORKSPACE (TESTING)

### Test Installation Flow

1. Navigate to **OAuth & Permissions**
2. Scroll up → Click **"Reinstall to Workspace"**
3. Review permissions → Click **"Allow"**
4. Slack redirects to your callback URL
5. You should be redirected to `/integrations?slack_connected=true`

### Test Commands

In any Slack channel:

**1. Slash Command**:
```
/ask What is 2nd Brain?
```

**2. Channel Mention**:
```
@2ndBrain What integrations are supported?
```

**3. Direct Message**:
```
[Open DM with 2nd Brain bot]
What is the pricing?
```

All three should:
- ✅ Trigger a search
- ✅ Return AI-generated answer
- ✅ Show source citations
- ✅ Include confidence score

---

## 7. SUBMIT FOR DISTRIBUTION

### Prerequisites

Before submitting to Slack App Directory:

✅ **App must be functional**
   - All features working
   - No broken links
   - Proper error handling

✅ **Security Review**
   - Use HTTPS everywhere
   - Verify request signatures
   - Handle tokens securely

✅ **Privacy Policy**
   - Create privacy policy page
   - Add link in app settings

✅ **Support Email**
   - Add support email in app settings

✅ **Terms of Service**
   - Create ToS page (optional but recommended)

### Step 1: Prepare for Review

Navigate to **Manage Distribution**:

**1. Add Privacy Policy URL**:
```
https://2ndbrain.io/privacy
```

**2. Add Support Email**:
```
support@2ndbrain.io
```

**3. Distribution Settings**:
- ✅ Remove Hard Coded Information
- ✅ Validate All Redirect URLs
- ✅ Implement Proper Token Rotation

### Step 2: Submit to Slack App Directory

Navigate to **Manage Distribution** → **Submit to App Directory**:

**What does your app do?**:
```
2nd Brain is an AI-powered knowledge assistant that helps teams find information instantly. Users can ask questions via /ask command, @mention the bot, or send direct messages. The bot searches your organization's knowledge base and returns AI-generated answers with source citations.
```

**What makes your app unique?**:
```
Unlike other knowledge bots, 2nd Brain:
1. Uses advanced RAG (Retrieval Augmented Generation) for accurate answers
2. Identifies knowledge gaps automatically
3. Includes hallucination detection for trust
4. Shows confidence scores with every answer
5. Integrates with multiple data sources (Gmail, Slack, Box, GitHub)
```

**Screenshots** (required):
1. Slash command in action (`/ask`)
2. Channel mention (`@2ndBrain`)
3. Answer with sources
4. Direct message example
5. Knowledge gaps view (optional)

**Video** (optional but recommended):
- 30-60 second demo
- Show all 3 interaction methods
- Highlight key features

Click **"Submit"**

### Step 3: Review Process

Slack reviews typically take **2-7 days**:

✅ **Automated Checks** (immediate):
   - Valid redirect URLs
   - HTTPS endpoints
   - Proper OAuth scopes

✅ **Manual Review** (2-7 days):
   - Functionality testing
   - Security review
   - User experience
   - Policy compliance

**Common rejection reasons**:
- Broken functionality
- Poor error handling
- Missing privacy policy
- Requesting excessive scopes
- Unclear value proposition

---

## 8. ADD "ADD TO SLACK" BUTTON

### Frontend Integration

Add this to your frontend (React/Next.js):

**File**: `frontend/components/integrations/SlackIntegration.tsx`

```tsx
import React from 'react'
import axios from 'axios'

export default function SlackIntegration() {
  const handleAddToSlack = async () => {
    // Trigger OAuth flow
    window.location.href = `${process.env.NEXT_PUBLIC_API_URL}/api/slack/oauth/install`
  }

  return (
    <div className="integration-card">
      <div className="flex items-center gap-4">
        <img src="/slack-icon.svg" alt="Slack" className="w-12 h-12" />

        <div className="flex-1">
          <h3 className="text-lg font-semibold">Slack Bot</h3>
          <p className="text-sm text-gray-600">
            Ask questions directly in Slack with /ask command or @mentions
          </p>
        </div>

        <button
          onClick={handleAddToSlack}
          className="flex items-center gap-2 px-4 py-2 bg-[#4A154B] text-white rounded hover:bg-[#611f69]"
        >
          <img src="/slack-logo-white.svg" alt="" className="w-5 h-5" />
          Add to Slack
        </button>
      </div>

      {/* Features */}
      <div className="mt-4 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-green-600">✓</span>
          <span>/ask command for instant answers</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-green-600">✓</span>
          <span>@mention bot in any channel</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-green-600">✓</span>
          <span>Direct messages for private queries</span>
        </div>
      </div>
    </div>
  )
}
```

### Official "Add to Slack" Button

Use Slack's official button:

```html
<a href="https://slack.com/oauth/v2/authorize?client_id=YOUR_CLIENT_ID&scope=app_mentions:read,channels:history,channels:read,chat:write,commands,im:history,im:read,im:write,users:read&redirect_uri=https://app.2ndbrain.io/api/slack/oauth/callback">
  <img
    alt="Add to Slack"
    height="40"
    width="139"
    src="https://platform.slack-edge.com/img/add_to_slack.png"
    srcSet="https://platform.slack-edge.com/img/add_to_slack.png 1x, https://platform.slack-edge.com/img/add_to_slack@2x.png 2x"
  />
</a>
```

Replace `YOUR_CLIENT_ID` with your actual Slack Client ID.

---

## 9. ENVIRONMENT VARIABLES

Add these to your `.env` or environment:

```bash
# Slack App Credentials
SLACK_CLIENT_ID=123456789.123456789
SLACK_CLIENT_SECRET=abcd1234efgh5678ijkl9012mnop
SLACK_SIGNING_SECRET=abcdef1234567890abcdef1234567890

# Slack Bot Token (from OAuth & Permissions page)
SLACK_BOT_TOKEN=xoxb-YOUR_TOKEN_HERE

# Frontend URL (for OAuth redirect)
FRONTEND_URL=https://app.2ndbrain.io
```

### Where to Find These

1. **Client ID & Client Secret**:
   - Navigate to **Basic Information** → **App Credentials**
   - Copy Client ID and Client Secret

2. **Signing Secret**:
   - Navigate to **Basic Information** → **App Credentials** → **Signing Secret**
   - Click "Show" → Copy

3. **Bot Token** (after installation):
   - Navigate to **OAuth & Permissions**
   - Copy **Bot User OAuth Token** (starts with `xoxb-`)

---

## 10. TESTING

### Test Checklist

**OAuth Flow**:
- ✅ Click "Add to Slack" redirects to Slack
- ✅ After authorization, redirects back to app
- ✅ Success message shown
- ✅ Bot appears in workspace

**Slash Command** (`/ask`):
- ✅ `/ask test query` triggers search
- ✅ Response appears within 3 seconds
- ✅ Answer is relevant
- ✅ Sources are shown
- ✅ Confidence score displayed

**Channel Mentions** (`@2ndBrain`):
- ✅ @2ndBrain mention triggers search
- ✅ Bot replies in thread
- ✅ Answer with sources
- ✅ Works in public channels
- ✅ Works in private channels (if bot is invited)

**Direct Messages**:
- ✅ DM to bot triggers search
- ✅ Bot responds with answer
- ✅ Works for any message (no @ needed)

**Error Handling**:
- ✅ No results found: Shows helpful message
- ✅ API error: Shows error message
- ✅ Timeout: Shows timeout message
- ✅ Signature verification failure: Returns 403

---

## PRODUCTION DEPLOYMENT

### Backend Updates

1. **Register Blueprint** (already done):
   ```python
   # app_v2.py
   from api.slack_bot_routes import slack_bot_bp
   app.register_blueprint(slack_bot_bp)
   ```

2. **Add to requirements.txt**:
   ```
   slack-sdk==3.23.0
   ```

3. **Install**:
   ```bash
   pip install slack-sdk
   ```

### HTTPS Requirement

Slack **requires HTTPS** for all endpoints:
- Use Let's Encrypt for free SSL
- Or deploy behind Cloudflare
- Or use ngrok for development

### ngrok for Development

```bash
# Install ngrok
brew install ngrok

# Start ngrok
ngrok http 5003

# Copy HTTPS URL (e.g., https://abc123.ngrok.io)
# Use this as Request URL in Slack app config
```

---

## SECURITY BEST PRACTICES

### 1. Verify Slack Requests

Always verify request signatures:
```python
from slack_sdk.signature import SignatureVerifier

verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

if not verifier.is_valid(body, timestamp, signature):
    return 403
```

### 2. Validate Timestamps

Prevent replay attacks:
```python
if abs(time.time() - int(timestamp)) > 60 * 5:  # 5 minutes
    return 403
```

### 3. Store Tokens Securely

- **Never** commit tokens to git
- Use environment variables
- Encrypt tokens in database
- Rotate tokens regularly

### 4. Implement Rate Limiting

Prevent abuse:
```python
from middleware.rate_limit import rate_limit_by_plan

@slack_bot_bp.route('/commands/ask', methods=['POST'])
@rate_limit_by_plan("slack_commands")  # Limit per tenant
def slack_command_ask():
    ...
```

---

## TROUBLESHOOTING

### Problem: OAuth redirect fails

**Solution**:
- Check redirect URL matches exactly in Slack app settings
- Ensure HTTPS (not HTTP)
- Check network/firewall rules

### Problem: Slash command doesn't work

**Solution**:
- Check Request URL in Slack app settings
- Ensure endpoint returns 200 within 3 seconds
- Check signature verification
- View Slack API logs (Basic Information → Event Subscriptions → Request Log)

### Problem: Events not received

**Solution**:
- Ensure Event Subscriptions Request URL is correct
- Check that endpoint responds to challenge
- Verify bot has necessary scopes
- Check Slack API logs

### Problem: "Not in channel" error

**Solution**:
- Bot must be invited to private channels: `/invite @2ndBrain`
- Public channels: Bot is automatically available

---

## NEXT STEPS

1. ✅ Create Slack app
2. ✅ Configure OAuth & permissions
3. ✅ Add slash command
4. ✅ Enable events
5. ✅ Test in development workspace
6. ⚠️ Add privacy policy page
7. ⚠️ Submit to App Directory
8. ⚠️ Add "Add to Slack" button to UI
9. ⚠️ Deploy to production

---

## SUPPORT

**Slack API Documentation**:
- https://api.slack.com/start
- https://api.slack.com/authentication/oauth-v2
- https://api.slack.com/interactivity/slash-commands
- https://api.slack.com/apis/connections/events-api

**2nd Brain Slack Bot**:
- Backend: `backend/services/slack_bot_service.py`
- Routes: `backend/api/slack_bot_routes.py`
- Docs: `SLACK_APP_SETUP.md` (this file)

**Questions?**
- Check Slack API logs (App Settings → Event Subscriptions → Request Log)
- Test with ngrok for local development
- Review Slack's app review checklist

---

**Last Updated**: January 29, 2026
**Status**: Implementation Complete, Ready for Deployment
