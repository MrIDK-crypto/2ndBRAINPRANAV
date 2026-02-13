"""
Semantic Chunking Module
Splits documents on natural boundaries instead of fixed token counts.
"""

import re
import tiktoken
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Chunk:
    """Represents a document chunk"""
    content: str
    chunk_id: str
    doc_id: str
    chunk_index: int
    metadata: Dict
    chunk_type: str  # 'section', 'paragraph', 'table', 'list', 'slide'
    parent_chunk_id: Optional[str] = None


class SemanticChunker:
    """
    Semantic chunking that respects document structure.

    Strategies:
    1. Section-based: Split on headers/sections
    2. Paragraph-based: Split on double newlines
    3. Slide-based: For PowerPoint content
    4. Table-aware: Keep tables together
    5. Hierarchical: Create parent + child chunks
    """

    # Chunk size limits - STRICT enforcement
    MAX_CHUNK_TOKENS = 800  # Reduced for better granularity
    MIN_CHUNK_TOKENS = 50   # Reduced to keep small but meaningful chunks
    OVERLAP_TOKENS = 50
    ABSOLUTE_MAX_TOKENS = 1500  # Hard limit - never exceed this

    # Section header patterns
    HEADER_PATTERNS = [
        r'^#{1,6}\s+.+$',  # Markdown headers
        r'^[A-Z][A-Z\s]{3,50}$',  # ALL CAPS headers
        r'^\d+\.\s+[A-Z].+$',  # Numbered sections
        r'^(?:SLIDE\s*\d+|Slide\s*\d+)',  # Slide markers
        r'^(?:Section|Chapter|Part)\s+\d+',  # Section markers
        r'^(?:Executive Summary|Introduction|Conclusion|Recommendation)',
        r'^(?:Problem Statement|Background|Analysis|Results|Discussion)',
        r'^(?:Financial Analysis|Market Analysis|Competitive Analysis)',
        r'^(?:Risks|Mitigation|Next Steps|Timeline|Budget)',
    ]

    # Table detection patterns
    TABLE_PATTERNS = [
        r'\|.*\|.*\|',  # Markdown tables
        r'^\s*[-+]+\s*$',  # Table borders
        r'\t\S+\t\S+',  # Tab-separated values
    ]

    # List detection patterns
    LIST_PATTERNS = [
        r'^[\s]*[-•*]\s+',  # Bullet lists
        r'^[\s]*\d+[\.\)]\s+',  # Numbered lists
        r'^[\s]*[a-z][\.\)]\s+',  # Lettered lists
    ]

    def __init__(self, model: str = "gpt-4"):
        self.tokenizer = tiktoken.encoding_for_model(model)

    def count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.tokenizer.encode(text))

    def detect_document_type(self, content: str, metadata: Dict = None) -> str:
        """Detect the type of document for appropriate chunking strategy"""
        if metadata:
            file_name = metadata.get('file_name', '').lower()
            if file_name.endswith('.pptx') or file_name.endswith('.ppt'):
                return 'presentation'
            if file_name.endswith('.xlsx') or file_name.endswith('.xls'):
                return 'spreadsheet'

        # Content-based detection
        if re.search(r'SLIDE\s*\d+|slide\s*\d+', content):
            return 'presentation'

        if len(re.findall(r'\|.*\|', content)) > 5:
            return 'table_heavy'

        if len(re.findall(r'^#{1,3}\s+', content, re.MULTILINE)) > 3:
            return 'markdown'

        return 'general'

    def find_section_breaks(self, content: str) -> List[int]:
        """Find positions where new sections begin"""
        breaks = [0]
        lines = content.split('\n')
        current_pos = 0

        for i, line in enumerate(lines):
            # Check if line matches any header pattern
            for pattern in self.HEADER_PATTERNS:
                if re.match(pattern, line.strip(), re.IGNORECASE):
                    if current_pos > 0:
                        breaks.append(current_pos)
                    break

            current_pos += len(line) + 1  # +1 for newline

        breaks.append(len(content))
        return sorted(set(breaks))

    def extract_slides(self, content: str) -> List[Dict]:
        """Extract slides from presentation content"""
        slides = []

        # Try to split by slide markers
        slide_pattern = r'(?:SLIDE\s*\d+|slide\s*\d+|---\s*slide\s*---)'
        parts = re.split(slide_pattern, content, flags=re.IGNORECASE)

        if len(parts) > 1:
            for i, part in enumerate(parts):
                if part.strip():
                    slides.append({
                        'index': i,
                        'content': part.strip(),
                        'type': 'slide'
                    })
        else:
            # Fall back to section-based chunking
            sections = self.find_section_breaks(content)
            for i in range(len(sections) - 1):
                section_content = content[sections[i]:sections[i+1]].strip()
                if section_content:
                    slides.append({
                        'index': i,
                        'content': section_content,
                        'type': 'section'
                    })

        return slides

    def extract_tables(self, content: str) -> List[Tuple[int, int, str]]:
        """Find and extract tables from content"""
        tables = []
        lines = content.split('\n')

        in_table = False
        table_start = 0
        table_lines = []
        current_pos = 0

        for i, line in enumerate(lines):
            is_table_line = any(re.search(p, line) for p in self.TABLE_PATTERNS)

            if is_table_line and not in_table:
                in_table = True
                table_start = current_pos
                table_lines = [line]
            elif is_table_line and in_table:
                table_lines.append(line)
            elif not is_table_line and in_table:
                # End of table
                if len(table_lines) > 2:  # Minimum table size
                    table_content = '\n'.join(table_lines)
                    tables.append((table_start, current_pos, table_content))
                in_table = False
                table_lines = []

            current_pos += len(line) + 1

        return tables

    def chunk_by_paragraphs(self, content: str, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Split content into paragraph-based chunks"""
        chunks = []

        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r'\n\s*\n', content)

        current_chunk_content = ""
        current_chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if adding this paragraph exceeds max tokens
            combined = current_chunk_content + "\n\n" + para if current_chunk_content else para
            combined_tokens = self.count_tokens(combined)

            if combined_tokens > self.MAX_CHUNK_TOKENS and current_chunk_content:
                # Save current chunk and start new one
                chunks.append(Chunk(
                    content=current_chunk_content,
                    chunk_id=f"{doc_id}_chunk_{current_chunk_idx}",
                    doc_id=doc_id,
                    chunk_index=current_chunk_idx,
                    metadata=metadata,
                    chunk_type='paragraph'
                ))
                current_chunk_idx += 1

                # Start new chunk with overlap from previous
                overlap_text = self._get_overlap_text(current_chunk_content)
                current_chunk_content = overlap_text + "\n\n" + para if overlap_text else para
            else:
                current_chunk_content = combined

        # Don't forget the last chunk
        if current_chunk_content:
            chunks.append(Chunk(
                content=current_chunk_content,
                chunk_id=f"{doc_id}_chunk_{current_chunk_idx}",
                doc_id=doc_id,
                chunk_index=current_chunk_idx,
                metadata=metadata,
                chunk_type='paragraph'
            ))

        return chunks

    def chunk_by_sections(self, content: str, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Split content into section-based chunks with hierarchy"""
        chunks = []
        section_breaks = self.find_section_breaks(content)

        for i in range(len(section_breaks) - 1):
            section_content = content[section_breaks[i]:section_breaks[i+1]].strip()

            if not section_content:
                continue

            section_tokens = self.count_tokens(section_content)

            if section_tokens <= self.MAX_CHUNK_TOKENS:
                # Section fits in one chunk
                chunks.append(Chunk(
                    content=section_content,
                    chunk_id=f"{doc_id}_section_{i}",
                    doc_id=doc_id,
                    chunk_index=i,
                    metadata=metadata,
                    chunk_type='section'
                ))
            else:
                # Section too large - create parent + children
                parent_id = f"{doc_id}_section_{i}_parent"

                # Parent chunk (summary/first part)
                parent_content = section_content[:2000]  # First ~500 tokens as summary
                chunks.append(Chunk(
                    content=parent_content,
                    chunk_id=parent_id,
                    doc_id=doc_id,
                    chunk_index=i,
                    metadata=metadata,
                    chunk_type='section_parent'
                ))

                # Child chunks (full content split by paragraphs)
                child_chunks = self.chunk_by_paragraphs(section_content, f"{doc_id}_section_{i}", metadata)
                for j, child in enumerate(child_chunks):
                    child.parent_chunk_id = parent_id
                    child.chunk_id = f"{doc_id}_section_{i}_child_{j}"
                    chunks.append(child)

        return chunks

    def chunk_presentation(self, content: str, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Chunk presentation content by slides"""
        chunks = []
        slides = self.extract_slides(content)

        for slide in slides:
            slide_content = slide['content']
            slide_tokens = self.count_tokens(slide_content)

            if slide_tokens <= self.MAX_CHUNK_TOKENS:
                chunks.append(Chunk(
                    content=slide_content,
                    chunk_id=f"{doc_id}_slide_{slide['index']}",
                    doc_id=doc_id,
                    chunk_index=slide['index'],
                    metadata={**metadata, 'slide_number': slide['index']},
                    chunk_type='slide'
                ))
            else:
                # Split large slides
                sub_chunks = self.chunk_by_paragraphs(slide_content, f"{doc_id}_slide_{slide['index']}", metadata)
                for j, sub in enumerate(sub_chunks):
                    sub.chunk_id = f"{doc_id}_slide_{slide['index']}_part_{j}"
                    sub.metadata['slide_number'] = slide['index']
                    chunks.append(sub)

        return chunks

    def _get_overlap_text(self, text: str, target_tokens: int = None) -> str:
        """Get the end portion of text for overlap"""
        if target_tokens is None:
            target_tokens = self.OVERLAP_TOKENS

        tokens = self.tokenizer.encode(text)
        if len(tokens) <= target_tokens:
            return text

        overlap_tokens = tokens[-target_tokens:]
        return self.tokenizer.decode(overlap_tokens)

    def chunk_document(self, content: str, doc_id: str, metadata: Dict = None) -> List[Chunk]:
        """
        Main chunking method - automatically selects best strategy.

        Args:
            content: Document text content
            doc_id: Unique document identifier
            metadata: Optional metadata dict

        Returns:
            List of Chunk objects
        """
        if metadata is None:
            metadata = {}

        # CRITICAL: Enforce absolute max token limit on input
        content_tokens = self.count_tokens(content)
        if content_tokens > 50000:  # Very large document
            # Split into manageable parts first
            content = self._split_large_content(content, doc_id, metadata)

        # Detect document type
        doc_type = self.detect_document_type(content, metadata)
        metadata['doc_type'] = doc_type

        # Select chunking strategy based on document type
        if doc_type == 'presentation':
            chunks = self.chunk_presentation(content, doc_id, metadata)
        elif doc_type in ['markdown', 'general']:
            # Try section-based first, fall back to paragraph
            chunks = self.chunk_by_sections(content, doc_id, metadata)
            if len(chunks) <= 1:
                chunks = self.chunk_by_paragraphs(content, doc_id, metadata)
        else:
            chunks = self.chunk_by_paragraphs(content, doc_id, metadata)

        # Ensure all chunks meet minimum size
        chunks = self._merge_small_chunks(chunks)

        # CRITICAL: Final pass to enforce max token limit
        chunks = self._enforce_max_tokens(chunks, doc_id, metadata)

        return chunks

    def _split_large_content(self, content: str, doc_id: str, metadata: Dict) -> str:
        """Split very large content into manageable parts"""
        # For now, just truncate with warning - proper handling would create multiple docs
        max_chars = self.ABSOLUTE_MAX_TOKENS * 4 * 30  # ~30 chunks worth
        if len(content) > max_chars:
            print(f"Warning: Truncating very large document {doc_id} from {len(content)} to {max_chars} chars")
            content = content[:max_chars]
        return content

    def _enforce_max_tokens(self, chunks: List[Chunk], doc_id: str, metadata: Dict) -> List[Chunk]:
        """Final pass to ensure no chunk exceeds absolute max tokens"""
        result = []
        for chunk in chunks:
            tokens = self.count_tokens(chunk.content)
            if tokens > self.ABSOLUTE_MAX_TOKENS:
                # Split this chunk
                sub_chunks = self._force_split_chunk(chunk, doc_id, metadata)
                result.extend(sub_chunks)
            else:
                result.append(chunk)

        # Re-index
        for i, chunk in enumerate(result):
            chunk.chunk_index = i

        return result

    def _force_split_chunk(self, chunk: Chunk, doc_id: str, metadata: Dict) -> List[Chunk]:
        """Force split a chunk that exceeds max tokens"""
        content = chunk.content
        tokens = self.tokenizer.encode(content)
        max_tokens = self.ABSOLUTE_MAX_TOKENS

        sub_chunks = []
        start = 0
        idx = 0

        while start < len(tokens):
            end = min(start + max_tokens, len(tokens))
            sub_content = self.tokenizer.decode(tokens[start:end])

            sub_chunks.append(Chunk(
                content=sub_content,
                chunk_id=f"{chunk.chunk_id}_split_{idx}",
                doc_id=doc_id,
                chunk_index=idx,
                metadata=metadata,
                chunk_type=f"{chunk.chunk_type}_split",
                parent_chunk_id=chunk.chunk_id
            ))

            start = end - self.OVERLAP_TOKENS  # Overlap
            idx += 1

        return sub_chunks

    def _merge_small_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Merge chunks that are too small"""
        if len(chunks) <= 1:
            return chunks

        merged = []
        current = None

        for chunk in chunks:
            chunk_tokens = self.count_tokens(chunk.content)

            if chunk_tokens < self.MIN_CHUNK_TOKENS:
                if current is None:
                    current = chunk
                else:
                    # Merge with current
                    current.content = current.content + "\n\n" + chunk.content
            else:
                if current is not None:
                    # Check if current + new chunk can be merged
                    combined_tokens = self.count_tokens(current.content + "\n\n" + chunk.content)
                    if combined_tokens <= self.MAX_CHUNK_TOKENS:
                        current.content = current.content + "\n\n" + chunk.content
                    else:
                        merged.append(current)
                        current = chunk
                else:
                    current = chunk

        if current is not None:
            merged.append(current)

        # Re-index chunks
        for i, chunk in enumerate(merged):
            chunk.chunk_index = i

        return merged

    def chunk_to_dict(self, chunk: Chunk) -> Dict:
        """Convert Chunk to dictionary for storage"""
        return {
            'chunk_id': chunk.chunk_id,
            'doc_id': chunk.doc_id,
            'content': chunk.content,
            'chunk_index': chunk.chunk_index,
            'metadata': chunk.metadata,
            'chunk_type': chunk.chunk_type,
            'parent_chunk_id': chunk.parent_chunk_id
        }


def create_chunker() -> SemanticChunker:
    """Factory function to create a SemanticChunker"""
    return SemanticChunker()


if __name__ == "__main__":
    # Test the chunker
    chunker = create_chunker()

    test_content = """
# Executive Summary

This project analyzes two service expansion options for UCLA Health.

## Problem Statement

UCLA Health faces significant over-capacity issues in NICU and L&D beds. This impacts patient safety and care quality.

Key statistics:
- 44/420 transfer NICU patients turned away (2019-2024)
- 288/420 transfer PICU patients turned away
- Lost opportunity cost: $632,553 annually

## Financial Analysis

### NICU Step-Down Financial Model

| Year | Revenue | ROI |
|------|---------|-----|
| 1    | $8.99M  | 14% |
| 2    | $9.44M  | 120%|
| 3    | $9.92M  | 125%|

Initial Investment: $2,441,300
NPV (7% discount rate): $6,855,853

## Recommendation

We recommend the creation of the OB-ED Unit based on:
1. Better long-term outcomes
2. Addresses L&D overcapacity
3. Improved patient care transition
"""

    chunks = chunker.chunk_document(test_content, "test_doc_001", {"file_name": "ucla_health.md"})

    print(f"Created {len(chunks)} chunks:")
    for chunk in chunks:
        tokens = chunker.count_tokens(chunk.content)
        print(f"\n[{chunk.chunk_id}] Type: {chunk.chunk_type}, Tokens: {tokens}")
        print(f"Content preview: {chunk.content[:100]}...")
