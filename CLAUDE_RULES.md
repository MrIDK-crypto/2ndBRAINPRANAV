# Claude Rules for 2ndBrainFINAL

## CRITICAL RULES - NEVER BREAK THESE

### 1. NEVER PUSH WITHOUT ASKING
- **ALWAYS** ask the user for confirmation before running `git push`
- Show them what will be pushed first (git diff, commit message)
- Wait for explicit "yes" or approval before pushing
- This applies to ALL pushes - no exceptions

### 2. NEVER BLAME CONFIGURATION/CREDENTIALS
- Everything is already set up and working
- If something doesn't work, the bug is in the CODE, not the config
- Don't suggest checking API keys, credentials, or environment variables
- Don't say "make sure X is configured" - it already is

### 3. THINK BEFORE MAKING CHANGES
- Read the code carefully before modifying
- Understand what exists before adding new code
- Don't introduce bugs by rushing
- Test changes locally before suggesting commits

### 4. DON'T BREAK EXISTING FUNCTIONALITY
- Always verify existing features still work after changes
- Run the app locally and test before committing
- If unsure, ask the user to verify

---

## Project Context

### Servers
- **Backend**: Flask on port 5003 (use `./venv_fixed/bin/python app_v2.py`)
- **Frontend**: Next.js on port 3006 or 3007

### Key Files Modified Recently
- `backend/services/code_gap_detector.py` - Contextual code gap detection
- `backend/services/sync_progress_service.py` - Fixed 'completed' vs 'complete' status
- `frontend/components/knowledge-gaps/KnowledgeGaps.tsx` - Fixed question field mismatch

### Known Issues Fixed
1. **Knowledge Gaps not displaying**: Field mismatch `question.text` vs `question.question`
2. **Email notifications not working**: GitHub sends `status='completed'` but service checked for `'complete'`
3. **Generic code gap questions**: Rewrote detector to generate contextual questions

---

## User Preferences
- Don't use emojis unless asked
- Be concise, don't over-explain
- Fix bugs properly, don't add workarounds
- Test locally before pushing to production
