# RAG Quality & File Parsing Robustness Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the RAG pipeline return specific, contextual answers instead of generic/vague ones, and ensure all advertised file types parse correctly without crashing on large files.

**Architecture:** Three improvement areas: (1) Better context assembly — give the LLM more content per source and smarter system prompts, (2) Robust file parsing — handle all advertised types with size guards and graceful degradation, (3) Query-aware retrieval — detect query intent and adapt search strategy.

**Tech Stack:** Flask, Azure OpenAI (GPT-5, text-embedding-3-large), Pinecone, PyPDF2, openpyxl, python-pptx, python-docx

---

## Current Problems (from investigation)

| Problem | Root Cause | Impact |
|---------|-----------|--------|
| Vague/generic RAG answers | Only 3,000 chars per source in context; 48K char total budget is underutilized | LLM doesn't have enough material to be specific |
| "I don't have information" when it does | `MIN_COSINE_SCORE = 0.20` filters out slightly-off but relevant results | Missed relevant content |
| No parsing for images (PNG/JPG) | Accepted in upload but never OCR'd/described | Silent data loss |
| No parsing for audio (MP3/WAV) | Accepted but never transcribed during upload | Silent data loss |
| No parsing for RTF files | Not in traditional parsers, depends on Azure/Docling | Fails silently |
| ZIP files not extracted | Uploaded as blob, never unpacked | Useless in KB |
| HTML files stored raw | Decoded as UTF-8 but full HTML tags left in | Noisy embeddings |
| JSON files stored raw | No structure extraction | Hard to search |
| No file size limit on upload endpoint | Large files can OOM the backend | Server crash |
| Conversation history underutilized | Only last 6 messages × 200 chars for context | Loses conversational thread |

---

## Task 1: Increase Context Quality for LLM

**Problem:** Each source only contributes 3,000 chars to context. With 15 sources × 3K = 45K chars, but many sources repeat similar info. The LLM gets breadth but not depth.

**Files:**
- Modify: `backend/services/enhanced_search_service.py`

**Step 1: Increase per-source context and reduce source count for depth**

In `generate_answer_stream()` and `generate_answer()`, change context assembly:

```python
# OLD: 15 sources × 3,000 chars = 45K (broad but shallow)
# NEW: 8 sources × 6,000 chars = 48K (fewer sources, more depth per source)
max_context_sources = 8  # was 15
max_chars_per_source = 6000  # was 3000
max_chars = 50000  # was 48000
```

**Step 2: Deduplicate overlapping chunks from the same document**

Before assembling context, group results by `doc_id` and merge overlapping chunks:

```python
def _merge_doc_chunks(self, results):
    """Merge chunks from same document into single richer context"""
    by_doc = {}
    for r in results:
        doc_id = r.get('doc_id', '')
        if doc_id not in by_doc:
            by_doc[doc_id] = r.copy()
        else:
            existing = by_doc[doc_id]
            existing_content = existing.get('content', '')
            new_content = r.get('content', '')
            # Only append if genuinely new content (not overlapping chunk)
            if new_content and new_content[:200] not in existing_content:
                existing['content'] = existing_content + '\n\n' + new_content
            # Keep better score
            existing['score'] = max(existing.get('score', 0), r.get('score', 0))
    return list(by_doc.values())
```

**Step 3: Improve system prompt to discourage vague answers**

Add to Mode 3 system prompt:

```python
"""
ANSWER QUALITY RULES:
- Be SPECIFIC. Use exact names, numbers, dates, and details from sources.
- NEVER say "various", "several", "multiple" when you can list the actual items.
- If the user asks "what files do I have" or "what's in my data", list them by name.
- If sources contain tables or structured data, reproduce the key data points.
- Prefer direct quotes and specific facts over summaries.
- If you only have partial information, say what you DO know specifically, then note what's missing.
"""
```

**Step 4: Commit**

```bash
git add backend/services/enhanced_search_service.py
git commit -m "feat: deeper context per source, chunk merging, anti-vague prompt"
```

---

## Task 2: Smarter Conversation History Usage

**Problem:** Only 6 messages × 200 chars for coreference resolution, and 4 messages × 500 chars in the API call. Users lose context in multi-turn conversations.

**Files:**
- Modify: `backend/services/enhanced_search_service.py`

**Step 1: Expand conversation history window**

```python
# In search_and_answer_stream():
MAX_HISTORY_MESSAGES = 20  # already 20, good
MAX_MESSAGE_LENGTH = 1000  # was 1000, good

# In generate_answer_stream() — increase what we send to LLM:
# OLD: last 4 messages × 500 chars
# NEW: last 8 messages × 800 chars
history_for_api = conversation_history[-8:]
for msg in history_for_api:
    content = str(msg.get('content', ''))[:800]
```

**Step 2: Add conversation summary for long chats**

When history > 10 messages, prepend a brief summary of the conversation topic:

```python
# Before assembling the API messages:
if len(conversation_history) > 10:
    topics = set()
    for msg in conversation_history:
        content = msg.get('content', '')[:200].lower()
        # Extract key nouns/phrases (simple heuristic)
        for word in content.split():
            if len(word) > 5 and word.isalpha():
                topics.add(word)
    if topics:
        topic_str = ', '.join(list(topics)[:10])
        summary_msg = f"[Conversation has covered: {topic_str}]"
        # Prepend as system context
```

**Step 3: Commit**

```bash
git add backend/services/enhanced_search_service.py
git commit -m "feat: expand conversation history window for better multi-turn"
```

---

## Task 3: Add File Size Limits and Graceful Degradation

**Problem:** No file size limit on upload. Large files can crash the server. The frontend advertises ZIP/image/audio support but the backend can't parse them.

**Files:**
- Modify: `backend/api/document_routes.py`
- Modify: `backend/parsers/document_parser.py`

**Step 1: Add file size validation to upload endpoint**

```python
# In upload_documents() and upload_and_embed():
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB
MAX_TOTAL_UPLOAD = 500 * 1024 * 1024  # 500 MB total per request

for file in files:
    file_content = file.read()
    if len(file_content) > MAX_FILE_SIZE:
        return jsonify({
            'success': False,
            'error': f'File "{file.filename}" exceeds 100 MB limit ({len(file_content) // (1024*1024)} MB)'
        }), 413
    file.seek(0)  # Reset for actual reading
```

**Step 2: Add per-parser size guards in DocumentParser**

```python
# In parse_file_bytes():
MAX_PARSE_SIZE = {
    '.pdf': 50 * 1024 * 1024,    # 50 MB
    '.docx': 50 * 1024 * 1024,
    '.pptx': 50 * 1024 * 1024,
    '.xlsx': 30 * 1024 * 1024,   # 30 MB (memory-intensive)
    '.csv': 30 * 1024 * 1024,
    '.txt': 20 * 1024 * 1024,    # 20 MB
    '.json': 20 * 1024 * 1024,
    '.xml': 20 * 1024 * 1024,
    '.html': 10 * 1024 * 1024,
}

def parse_file_bytes(self, file_bytes, filename):
    ext = Path(filename).suffix.lower()
    max_size = MAX_PARSE_SIZE.get(ext, 50 * 1024 * 1024)
    if len(file_bytes) > max_size:
        size_mb = len(file_bytes) / (1024 * 1024)
        limit_mb = max_size / (1024 * 1024)
        return f"[File too large to parse: {filename} ({size_mb:.1f} MB, limit {limit_mb:.0f} MB). Metadata stored but content not indexed.]"
    # ... rest of parsing
```

**Step 3: Add PDF page limit for very large PDFs**

```python
# In _parse_pdf():
MAX_PDF_PAGES = 500

with open(file_path, 'rb') as f:
    pdf_reader = PyPDF2.PdfReader(f)
    num_pages = min(len(pdf_reader.pages), MAX_PDF_PAGES)
    if len(pdf_reader.pages) > MAX_PDF_PAGES:
        text_parts.append(f"[NOTE: PDF has {len(pdf_reader.pages)} pages. Only first {MAX_PDF_PAGES} pages indexed.]")
```

**Step 4: Commit**

```bash
git add backend/api/document_routes.py backend/parsers/document_parser.py
git commit -m "feat: file size limits and graceful degradation for large files"
```

---

## Task 4: Add HTML Cleaning and JSON/XML Structure Extraction

**Problem:** HTML files are stored with all tags. JSON is stored as raw text. Both create noisy embeddings.

**Files:**
- Modify: `backend/parsers/document_parser.py`

**Step 1: Add HTML tag stripping**

```python
def _parse_html_bytes(self, file_bytes):
    """Extract clean text from HTML"""
    try:
        from bs4 import BeautifulSoup
        html = file_bytes.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script, style, nav, footer elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        # Collapse multiple blank lines
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text
    except Exception:
        return file_bytes.decode('utf-8', errors='ignore')
```

**Step 2: Add JSON structure extraction**

```python
def _parse_json_bytes(self, file_bytes):
    """Extract readable content from JSON"""
    import json
    try:
        data = json.loads(file_bytes.decode('utf-8', errors='ignore'))
        return self._json_to_text(data, max_depth=5)
    except json.JSONDecodeError:
        return file_bytes.decode('utf-8', errors='ignore')

def _json_to_text(self, data, max_depth=5, depth=0, prefix=''):
    """Convert JSON structure to readable text"""
    if depth > max_depth:
        return '[nested data truncated]'
    parts = []
    if isinstance(data, dict):
        for key, value in list(data.items())[:100]:  # Limit keys
            if isinstance(value, (dict, list)):
                parts.append(f"{prefix}{key}:")
                parts.append(self._json_to_text(value, max_depth, depth+1, prefix+'  '))
            else:
                parts.append(f"{prefix}{key}: {value}")
    elif isinstance(data, list):
        for i, item in enumerate(data[:200]):  # Limit array items
            parts.append(f"{prefix}[{i}] {self._json_to_text(item, max_depth, depth+1, prefix+'  ')}")
    else:
        return str(data)
    return '\n'.join(parts)
```

**Step 3: Add XML text extraction**

```python
def _parse_xml_bytes(self, file_bytes):
    """Extract text content from XML"""
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(file_bytes.decode('utf-8', errors='ignore'))
        texts = []
        for elem in root.iter():
            if elem.text and elem.text.strip():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                texts.append(f"{tag}: {elem.text.strip()}")
            if elem.tail and elem.tail.strip():
                texts.append(elem.tail.strip())
        return '\n'.join(texts[:5000])  # Limit output
    except Exception:
        return file_bytes.decode('utf-8', errors='ignore')
```

**Step 4: Wire into parse_file_bytes()**

```python
# Replace the plain text block:
if ext == '.html' or ext == '.htm':
    return self._parse_html_bytes(file_bytes)
elif ext == '.json':
    return self._parse_json_bytes(file_bytes)
elif ext == '.xml':
    return self._parse_xml_bytes(file_bytes)
elif ext in ('.txt', '.md'):
    return file_bytes.decode('utf-8', errors='ignore')
```

**Step 5: Commit**

```bash
git add backend/parsers/document_parser.py
git commit -m "feat: clean HTML/JSON/XML parsing for better embeddings"
```

---

## Task 5: Add RTF Parsing Support

**Problem:** RTF files are advertised as supported but have no parser.

**Files:**
- Modify: `backend/parsers/document_parser.py`

**Step 1: Add RTF parser**

```python
# Add to parse_file_bytes() before the temp file fallback:
if ext == '.rtf':
    return self._parse_rtf_bytes(file_bytes)

def _parse_rtf_bytes(self, file_bytes):
    """Extract text from RTF files"""
    try:
        from striprtf.striprtf import rtf_to_text
        rtf_content = file_bytes.decode('utf-8', errors='ignore')
        return rtf_to_text(rtf_content)
    except ImportError:
        # Fallback: crude RTF tag stripping
        import re
        text = file_bytes.decode('utf-8', errors='ignore')
        text = re.sub(r'\\[a-z]+\d*\s?', '', text)
        text = re.sub(r'[{}]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text if len(text) > 20 else None
    except Exception:
        return None
```

**Step 2: Add striprtf to requirements**

```bash
echo "striprtf" >> backend/requirements.txt
```

**Step 3: Commit**

```bash
git add backend/parsers/document_parser.py backend/requirements.txt
git commit -m "feat: add RTF file parsing support"
```

---

## Task 6: Add Image Description via Azure GPT-4o Vision

**Problem:** PNG/JPG/GIF files are accepted but never processed — complete data loss.

**Files:**
- Modify: `backend/parsers/document_parser.py`

**Step 1: Add image description using Azure GPT-4o vision**

```python
def _parse_image_bytes(self, file_bytes, filename):
    """Describe image content using GPT-4o vision"""
    import base64
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT'),
            api_key=os.environ.get('AZURE_OPENAI_API_KEY'),
            api_version="2024-12-01-preview"
        )
        b64 = base64.b64encode(file_bytes).decode('utf-8')
        ext = Path(filename).suffix.lower().lstrip('.')
        mime = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif'}.get(ext, 'image/png')

        response = client.chat.completions.create(
            model="gpt-5-chat",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in detail. Include any text, labels, data, charts, diagrams, or notable content. Be thorough and specific."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
                ]
            }],
            max_tokens=1000
        )
        description = response.choices[0].message.content
        return f"[Image: {filename}]\n{description}"
    except Exception as e:
        print(f"[DocumentParser] Image parsing error for {filename}: {e}")
        return f"[Image file: {filename} — could not extract content]"
```

**Step 2: Wire into parse_file_bytes()**

```python
# Add before the temp file block:
if ext in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'):
    # Limit image size for vision API (max ~20MB base64)
    if len(file_bytes) > 20 * 1024 * 1024:
        return f"[Image file: {filename} — too large for vision analysis ({len(file_bytes) // (1024*1024)} MB)]"
    return self._parse_image_bytes(file_bytes, filename)
```

**Step 3: Commit**

```bash
git add backend/parsers/document_parser.py
git commit -m "feat: image content extraction via GPT-4o vision"
```

---

## Task 7: Add Audio Transcription on Upload

**Problem:** Audio/video files are accepted but never transcribed. Whisper endpoint exists but isn't used during upload.

**Files:**
- Modify: `backend/parsers/document_parser.py`

**Step 1: Add audio transcription using Azure Whisper**

```python
def _parse_audio_bytes(self, file_bytes, filename):
    """Transcribe audio using Azure Whisper"""
    ext = Path(filename).suffix.lower()
    try:
        from openai import AzureOpenAI
        client = AzureOpenAI(
            azure_endpoint=os.environ.get('AZURE_OPENAI_ENDPOINT'),
            api_key=os.environ.get('AZURE_OPENAI_API_KEY'),
            api_version="2024-12-01-preview"
        )

        # Whisper has a 25 MB limit
        if len(file_bytes) > 25 * 1024 * 1024:
            return f"[Audio file: {filename} — too large for transcription ({len(file_bytes) // (1024*1024)} MB, limit 25 MB)]"

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            with open(tmp_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper",
                    file=audio_file,
                    response_format="text"
                )
            return f"[Audio transcription: {filename}]\n{transcript}"
        finally:
            os.unlink(tmp_path)
    except Exception as e:
        print(f"[DocumentParser] Audio transcription error for {filename}: {e}")
        return f"[Audio file: {filename} — transcription failed: {str(e)[:100]}]"
```

**Step 2: Wire into parse_file_bytes()**

```python
# Add before the temp file block:
audio_exts = ('.mp3', '.wav', '.m4a', '.webm', '.mp4', '.mov', '.ogg', '.flac')
if ext in audio_exts:
    return self._parse_audio_bytes(file_bytes, filename)
```

**Step 3: Commit**

```bash
git add backend/parsers/document_parser.py
git commit -m "feat: audio/video transcription on upload via Whisper"
```

---

## Task 8: Add ZIP File Extraction

**Problem:** ZIP files are accepted but stored as blobs, never extracted.

**Files:**
- Modify: `backend/api/document_routes.py`

**Step 1: Add ZIP extraction in upload endpoint**

```python
import zipfile

# In upload_documents(), before the main file processing loop:
def extract_zip(file_content, filename):
    """Extract files from ZIP and return list of (name, bytes) tuples"""
    extracted = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if info.file_size > 100 * 1024 * 1024:  # Skip files > 100MB
                    continue
                if info.filename.startswith('__MACOSX') or info.filename.startswith('.'):
                    continue
                inner_bytes = zf.read(info.filename)
                inner_name = os.path.basename(info.filename)
                if inner_name:
                    extracted.append((inner_name, inner_bytes))
    except zipfile.BadZipFile:
        pass
    return extracted[:50]  # Max 50 files from a ZIP

# In the file processing loop, replace ZIP handling:
if filename.lower().endswith('.zip'):
    inner_files = extract_zip(file_content, filename)
    for inner_name, inner_bytes in inner_files:
        # Process each extracted file as if uploaded individually
        # (reuse existing parsing logic)
```

**Step 2: Commit**

```bash
git add backend/api/document_routes.py
git commit -m "feat: extract and index files from ZIP uploads"
```

---

## Task 9: Lower MIN_COSINE_SCORE and Improve Fallback

**Problem:** `MIN_COSINE_SCORE = 0.20` is too aggressive — filters out relevant results for unusual queries. Users see "I don't have information" when the KB does have relevant content.

**Files:**
- Modify: `backend/services/enhanced_search_service.py`

**Step 1: Lower threshold and add fallback**

```python
# Change from:
MIN_COSINE_SCORE = 0.20
# To:
MIN_COSINE_SCORE = 0.12  # More permissive — let reranking decide

# Also change the post-filter logic:
filtered = [r for r in initial_results if r.get('score', 0) >= MIN_COSINE_SCORE]
if not filtered and initial_results:
    # Keep top 3 results even if below threshold (let reranker decide)
    filtered = sorted(initial_results, key=lambda x: x.get('score', 0), reverse=True)[:3]
initial_results = filtered
```

**Step 2: When no results found at all, search with simplified query**

```python
# After initial search returns 0 results:
if not initial_results:
    # Try simplified query (just key nouns)
    simplified = ' '.join([w for w in query.split() if len(w) > 3 and w[0].isupper() or w.isdigit()])
    if simplified and simplified != query:
        initial_results = vector_store.hybrid_search(
            query=simplified, tenant_id=tenant_id, top_k=top_k
        )
```

**Step 3: Commit**

```bash
git add backend/services/enhanced_search_service.py
git commit -m "fix: lower cosine threshold and add simplified-query fallback"
```

---

## Task 10: Build, Deploy, Verify

**Files:**
- No code changes — build and deploy

**Step 1: Build backend**

```bash
docker build --platform linux/amd64 --no-cache -t 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest -f backend/Dockerfile backend/
```

**Step 2: Push to ECR**

```bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 923028187100.dkr.ecr.us-east-2.amazonaws.com
docker push 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest
```

**Step 3: Deploy to ECS**

```bash
aws ecs update-service --cluster secondbrain-cluster --service secondbrain-backend --force-new-deployment --region us-east-2
```

**Step 4: Verify**

```bash
aws ecs describe-services --cluster secondbrain-cluster --services secondbrain-backend --region us-east-2 --query 'services[0].deployments[*].rolloutState'
```

---

## Summary

| Task | What | Impact |
|------|------|--------|
| 1 | Deeper context per source + chunk merging + anti-vague prompt | **Specific answers instead of generic** |
| 2 | More conversation history to LLM | **Better multi-turn conversations** |
| 3 | File size limits + graceful degradation | **No more server crashes** |
| 4 | HTML/JSON/XML cleaning | **Cleaner embeddings** |
| 5 | RTF parsing | **New file type supported** |
| 6 | Image description via GPT-4o vision | **Images become searchable** |
| 7 | Audio transcription via Whisper | **Audio/video become searchable** |
| 8 | ZIP extraction | **ZIP contents indexed** |
| 9 | Lower cosine threshold + fallback | **Fewer "no results" responses** |
| 10 | Build and deploy | **Ship it** |
