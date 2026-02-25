"""
Progressive Summarization Service for 2nd Brain

Multi-level distillation of documents:
  L0: Raw content (already stored in Document.content)
  L1: Structured summary (already stored in Document.structured_summary via ExtractionService)
  L2: Key highlights with importance scoring (TF-IDF + topic matching, no GPT)
  L3: Executive summary - 3 sentences max (gpt-4o-mini)
  L4: One-liner - single sentence, max 200 chars (gpt-4o-mini)
"""

import re
import math
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from collections import Counter

from database.models import SessionLocal, Document, utc_now


def _utc_now():
    return datetime.now(timezone.utc)


class ProgressiveSummaryService:
    """Generate progressive summary levels for documents."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from services.openai_client import get_openai_client
                self._client = get_openai_client()
            except Exception as e:
                print(f"[ProgressiveSummary] Could not initialize OpenAI client: {e}")
        return self._client

    # ---- L2: Highlights (no GPT, TF-IDF based) ----

    def _tokenize(self, text: str) -> List[str]:
        """Simple word tokenization."""
        return re.findall(r'\b[a-z]{2,}\b', text.lower())

    def _compute_tfidf_sentences(self, content: str, topic_words: List[str] = None) -> List[Dict[str, Any]]:
        """
        Score sentences by TF-IDF importance + topic relevance.
        Returns ranked highlights without calling GPT.
        """
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', content.strip())
        if not sentences:
            return []

        # Filter too-short or too-long sentences
        sentences = [s.strip() for s in sentences if 20 < len(s.strip()) < 500]
        if not sentences:
            return []

        # Document-level word frequencies (TF)
        all_words = self._tokenize(content)
        word_count = Counter(all_words)
        total_words = len(all_words) or 1

        # IDF approximation: treat each sentence as a "document"
        doc_freq = Counter()
        sent_tokens = []
        for sent in sentences:
            tokens = set(self._tokenize(sent))
            sent_tokens.append(tokens)
            for token in tokens:
                doc_freq[token] += 1

        num_sents = len(sentences)

        # Topic boost words (from structured_summary key_topics)
        topic_set = set()
        if topic_words:
            for tw in topic_words:
                topic_set.update(self._tokenize(tw))

        # Stop words to ignore
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can',
            'had', 'her', 'was', 'one', 'our', 'out', 'has', 'have', 'been',
            'would', 'will', 'each', 'make', 'like', 'been', 'this', 'that',
            'with', 'they', 'from', 'some', 'what', 'there', 'when', 'which',
            'their', 'said', 'than', 'into', 'them', 'then', 'also', 'just',
            'about', 'more', 'other', 'could', 'after', 'those', 'should',
        }

        # Score each sentence
        scored = []
        for i, (sent, tokens) in enumerate(zip(sentences, sent_tokens)):
            if not tokens:
                continue

            # TF-IDF score
            score = 0.0
            for token in tokens:
                if token in stop_words:
                    continue
                tf = word_count.get(token, 0) / total_words
                idf = math.log((num_sents + 1) / (doc_freq.get(token, 1) + 1)) + 1
                score += tf * idf

            # Normalize by sentence length
            score = score / (len(tokens) ** 0.5) if tokens else 0

            # Topic boost: sentences matching key topics get 1.5x
            topic_overlap = len(tokens & topic_set)
            if topic_overlap > 0:
                score *= (1.0 + 0.5 * min(topic_overlap, 3))

            # Position bias: first and last 20% of document get slight boost
            position_ratio = i / max(num_sents - 1, 1)
            if position_ratio < 0.2 or position_ratio > 0.8:
                score *= 1.15

            scored.append({
                "text": sent,
                "importance": round(score, 4),
                "position": i,
            })

        # Sort by importance descending, take top 10-15
        scored.sort(key=lambda x: x["importance"], reverse=True)
        top_highlights = scored[:15]

        # Normalize importance to 0-1 range
        if top_highlights:
            max_score = top_highlights[0]["importance"]
            if max_score > 0:
                for h in top_highlights:
                    h["importance"] = round(h["importance"] / max_score, 2)

        # Re-sort by document position for readability
        top_highlights.sort(key=lambda x: x["position"])

        return [{"text": h["text"], "importance": h["importance"]} for h in top_highlights]

    # ---- L3: Executive summary (GPT) ----

    def _generate_l3(self, content: str, structured_summary: dict = None) -> Optional[str]:
        """Generate a 3-sentence executive summary using GPT."""
        client = self._get_client()
        if not client:
            return None

        # Use structured summary if available for cheaper/faster generation
        if structured_summary:
            context = json.dumps({
                "summary": structured_summary.get("summary", ""),
                "key_topics": structured_summary.get("key_topics", []),
                "decisions": structured_summary.get("decisions", []),
                "action_items": structured_summary.get("action_items", []),
            })
            prompt = f"Based on this extracted information, write exactly 3 concise sentences that capture the essential meaning:\n\n{context}"
        else:
            # Fall back to raw content (truncated)
            truncated = content[:8000] if content else ""
            prompt = f"Read this document and write exactly 3 concise sentences that capture the essential meaning:\n\n{truncated}"

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a precise summarizer. Write exactly 3 sentences. No preamble, no bullet points, just 3 clear sentences."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=200,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[ProgressiveSummary] L3 generation error: {e}")
            return None

    # ---- L4: One-liner (GPT) ----

    def _generate_l4(self, l3_summary: str = None, content: str = None, structured_summary: dict = None) -> Optional[str]:
        """Generate a single-sentence summary, max 200 chars."""
        client = self._get_client()
        if not client:
            return None

        # Prefer L3 as input (already distilled)
        if l3_summary:
            source_text = l3_summary
        elif structured_summary:
            source_text = structured_summary.get("summary", "")
        elif content:
            source_text = content[:4000]
        else:
            return None

        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Distill the input into ONE sentence, maximum 180 characters. Be specific, not generic. No preamble."},
                    {"role": "user", "content": source_text},
                ],
                temperature=0.1,
                max_tokens=60,
            )
            result = response.choices[0].message.content.strip()
            # Enforce 200 char limit
            if len(result) > 200:
                result = result[:197] + "..."
            return result
        except Exception as e:
            print(f"[ProgressiveSummary] L4 generation error: {e}")
            return None

    # ---- Public API ----

    def generate_summaries(
        self,
        document: Document,
        levels: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate progressive summary levels for a document.

        Args:
            document: Document ORM instance (must have content loaded)
            levels: Which levels to generate. Default: ["l2", "l3", "l4"]

        Returns: {"l2": [...], "l3": "...", "l4": "..."}
        """
        if levels is None:
            levels = ["l2", "l3", "l4"]

        result = {}
        content = document.content or ""
        structured = document.structured_summary or {}
        topic_words = structured.get("key_topics", [])

        if "l2" in levels:
            result["l2"] = self._compute_tfidf_sentences(content, topic_words)

        if "l3" in levels:
            result["l3"] = self._generate_l3(content, structured or None)

        if "l4" in levels:
            # Chain: use L3 if just generated
            l3_text = result.get("l3") or document.summary_l3_executive
            result["l4"] = self._generate_l4(
                l3_summary=l3_text,
                content=content,
                structured_summary=structured or None,
            )

        return result

    def generate_and_save(
        self,
        document_id: str,
        tenant_id: str,
        db,
        levels: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate summaries and persist to database.

        Returns the generated summaries dict.
        """
        doc = (
            db.query(Document)
            .filter(Document.id == document_id, Document.tenant_id == tenant_id)
            .first()
        )
        if not doc:
            return {"error": "Document not found"}

        if not doc.content or len(doc.content.strip()) < 50:
            return {"error": "Document content too short for summarization"}

        summaries = self.generate_summaries(doc, levels)

        if "l2" in summaries and summaries["l2"]:
            doc.summary_l2_highlights = summaries["l2"]
        if "l3" in summaries and summaries["l3"]:
            doc.summary_l3_executive = summaries["l3"]
        if "l4" in summaries and summaries["l4"]:
            doc.summary_l4_oneliner = summaries["l4"]

        doc.summary_levels_generated_at = _utc_now()
        doc.updated_at = utc_now()
        db.commit()

        return summaries

    def bulk_generate(
        self,
        tenant_id: str,
        db,
        force: bool = False,
        limit: int = 50,
        levels: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate summaries for documents that don't have them yet.

        Args:
            tenant_id: Tenant ID
            db: Database session
            force: Regenerate even if already present
            limit: Max documents to process in one batch
            levels: Which levels to generate

        Returns: {"processed": int, "skipped": int, "errors": int}
        """
        query = (
            db.query(Document)
            .filter(
                Document.tenant_id == tenant_id,
                Document.is_deleted == False,
                Document.content.isnot(None),
            )
        )

        if not force:
            query = query.filter(Document.summary_levels_generated_at.is_(None))

        documents = query.order_by(Document.created_at.desc()).limit(limit).all()

        processed = 0
        skipped = 0
        errors = 0

        for doc in documents:
            if not doc.content or len(doc.content.strip()) < 50:
                skipped += 1
                continue

            try:
                summaries = self.generate_summaries(doc, levels)

                if "l2" in summaries and summaries["l2"]:
                    doc.summary_l2_highlights = summaries["l2"]
                if "l3" in summaries and summaries["l3"]:
                    doc.summary_l3_executive = summaries["l3"]
                if "l4" in summaries and summaries["l4"]:
                    doc.summary_l4_oneliner = summaries["l4"]

                doc.summary_levels_generated_at = _utc_now()
                doc.updated_at = utc_now()
                processed += 1

            except Exception as e:
                print(f"[ProgressiveSummary] Error processing {doc.id[:8]}: {e}")
                errors += 1

        if processed > 0:
            db.commit()
            print(f"[ProgressiveSummary] Bulk: {processed} processed, {skipped} skipped, {errors} errors for tenant {tenant_id[:8]}")

        return {"processed": processed, "skipped": skipped, "errors": errors}
