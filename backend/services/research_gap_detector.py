"""
Research Lab Knowledge Gap Detector
====================================

Multi-source knowledge gap detection specifically designed for research labs.
Works across protocols, Slack messages, emails, Notion pages, GitHub code, and papers.

Key Features:
- LLM-guided detection (not hardcoded patterns)
- Cross-source contradiction detection
- Person-locked knowledge identification
- Unanswered question mining
- Protocol completeness checking
- Tribal knowledge capture

Architecture:
- Phase 1: Document Understanding (extract entities, questions, answers)
- Phase 2: Cross-Source Analysis (find contradictions, missing links)
- Phase 3: Source-Specific Analysis (protocol gaps, code docs, etc.)
- Phase 4: Knowledge Graph Gaps (bus factor, missing documentation)
"""

import logging
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime

from services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """An entity extracted from a document"""
    name: str
    entity_type: str  # reagent, equipment, cell_line, person, method, software
    mentions: List[Dict] = field(default_factory=list)  # [{doc_id, context, value}]


@dataclass
class ExtractedQuestion:
    """A question found in a document"""
    question_text: str
    doc_id: str
    doc_type: str
    has_answer: bool = False
    answer_text: Optional[str] = None
    answer_doc_id: Optional[str] = None


@dataclass
class DetectedGap:
    """A detected knowledge gap"""
    gap_type: str
    title: str
    description: str
    evidence: List[str]
    source_docs: List[str]
    questions: List[str]
    priority: int  # 1-5
    category: str


class ResearchGapDetector:
    """
    Multi-source knowledge gap detector for research labs.

    Uses LLM to understand documents contextually rather than
    relying on hardcoded patterns.
    """

    # Document type definitions
    DOC_TYPES = {
        'protocol': 'Step-by-step experimental procedures',
        'email': 'Email communications',
        'slack': 'Slack/chat messages',
        'notion': 'Notion pages and notes',
        'github': 'Code repositories and documentation',
        'paper': 'Published research papers',
        'lab_notebook': 'Lab notebook entries',
        'presentation': 'Slides and presentations',
        'other': 'Other documentation'
    }

    # Gap categories
    GAP_CATEGORIES = {
        'protocol_incomplete': 'Protocol missing critical details',
        'chat_not_documented': 'Information in chat not in official docs',
        'question_unanswered': 'Question asked but never answered',
        'contradiction': 'Conflicting information across sources',
        'reference_missing': 'Referenced document/method does not exist',
        'person_locked': 'Knowledge locked in one person',
        'code_undocumented': 'Code without documentation',
        'method_no_protocol': 'Method used but no protocol exists',
        'outdated': 'Information appears outdated',
        'tribal_knowledge': 'Informal knowledge not documented',
        'reproducibility_risk': 'Missing info needed for reproducibility',
        'troubleshooting_missing': 'No guidance for when things fail',
        'statistical_unclear': 'Statistical methods not justified',
        'time_sensitive': 'Time-dependent info not tracked'
    }

    def __init__(self):
        self._client = None
        self.documents = []
        self.entities = defaultdict(list)  # entity_name -> [mentions]
        self.questions = []
        self.gaps = []

    @property
    def client(self):
        if self._client is None:
            self._client = get_openai_client()
        return self._client

    def add_document(self, doc_id: str, title: str, content: str,
                     doc_type: str = 'other', metadata: Dict = None):
        """Add a document for analysis"""
        self.documents.append({
            'id': doc_id,
            'title': title,
            'content': content[:50000],  # Limit content size
            'doc_type': doc_type,
            'metadata': metadata or {}
        })

    def clear(self):
        """Clear all documents and reset state"""
        self.documents = []
        self.entities = defaultdict(list)
        self.questions = []
        self.gaps = []

    def analyze(self) -> Dict[str, Any]:
        """
        Run full multi-source gap analysis.

        Returns:
            Dict with gaps, stats, and recommendations
        """
        if not self.documents:
            return {'gaps': [], 'stats': {}, 'error': 'No documents to analyze'}

        logger.info(f"[ResearchGapDetector] Starting analysis of {len(self.documents)} documents")

        # Phase 1: Extract entities and questions from each document
        logger.info("[ResearchGapDetector] Phase 1: Document Understanding")
        self._phase1_extract_all()

        # Phase 2: Cross-source analysis
        logger.info("[ResearchGapDetector] Phase 2: Cross-Source Analysis")
        self._phase2_cross_source()

        # Phase 3: Source-specific analysis
        logger.info("[ResearchGapDetector] Phase 3: Source-Specific Analysis")
        self._phase3_source_specific()

        # Phase 4: Knowledge graph gaps
        logger.info("[ResearchGapDetector] Phase 4: Knowledge Graph Gaps")
        self._phase4_knowledge_graph()

        # Deduplicate and prioritize gaps
        self._deduplicate_gaps()
        self._prioritize_gaps()

        logger.info(f"[ResearchGapDetector] Analysis complete: {len(self.gaps)} gaps found")

        return {
            'gaps': [self._gap_to_dict(g) for g in self.gaps],
            'stats': {
                'documents_analyzed': len(self.documents),
                'entities_extracted': len(self.entities),
                'questions_found': len(self.questions),
                'gaps_detected': len(self.gaps),
                'by_category': self._count_by_category()
            }
        }

    def _phase1_extract_all(self):
        """Phase 1: Extract entities, questions, and key info from all documents"""

        # Group documents for batch processing (max 5 at a time for context limits)
        batch_size = 3
        for i in range(0, len(self.documents), batch_size):
            batch = self.documents[i:i+batch_size]
            self._extract_from_batch(batch)

    def _extract_from_batch(self, docs: List[Dict]):
        """Extract entities and questions from a batch of documents"""

        docs_text = ""
        for doc in docs:
            docs_text += f"\n\n=== DOCUMENT: {doc['title']} (Type: {doc['doc_type']}) ===\n"
            docs_text += doc['content'][:15000]  # Limit per doc

        prompt = f"""Analyze these research lab documents and extract:

1. ENTITIES: All reagents, equipment, cell lines, people, methods, and software mentioned
2. QUESTIONS: Any questions asked (in emails, Slack, etc.)
3. ANSWERS: Any answers provided to questions
4. CORRECTIONS: Any corrections or updates mentioned (e.g., "actually use X instead of Y")
5. REFERENCES: References to other documents, protocols, or methods
6. TRIBAL KNOWLEDGE: Informal tips, tricks, or knowledge shared

DOCUMENTS:
{docs_text}

Respond in JSON format:
{{
    "entities": [
        {{"name": "...", "type": "reagent|equipment|cell_line|person|method|software", "context": "...", "value": "optional value/concentration"}}
    ],
    "questions": [
        {{"question": "...", "asked_by": "optional", "has_answer": true/false, "answer": "if answered"}}
    ],
    "corrections": [
        {{"original": "...", "corrected": "...", "reason": "optional"}}
    ],
    "references": [
        {{"name": "...", "type": "protocol|method|document", "exists_in_docs": true/false}}
    ],
    "tribal_knowledge": [
        {{"tip": "...", "context": "..."}}
    ]
}}
"""

        try:
            response = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a research lab documentation expert. Extract structured information from lab documents."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=4000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Store extracted entities
            for entity in result.get('entities', []):
                self.entities[entity['name'].lower()].append({
                    'doc_ids': [d['id'] for d in docs],
                    'type': entity.get('type', 'unknown'),
                    'context': entity.get('context', ''),
                    'value': entity.get('value')
                })

            # Store questions
            for q in result.get('questions', []):
                self.questions.append(ExtractedQuestion(
                    question_text=q['question'],
                    doc_id=docs[0]['id'],
                    doc_type=docs[0]['doc_type'],
                    has_answer=q.get('has_answer', False),
                    answer_text=q.get('answer')
                ))

            # Create gaps from corrections (contradiction type)
            for correction in result.get('corrections', []):
                self.gaps.append(DetectedGap(
                    gap_type='contradiction',
                    title=f"Correction needed: {correction.get('original', 'value')[:50]}",
                    description=f"Original: {correction.get('original')}\nCorrected to: {correction.get('corrected')}\nReason: {correction.get('reason', 'Not specified')}",
                    evidence=[f"Correction found in: {docs[0]['title']}"],
                    source_docs=[d['id'] for d in docs],
                    questions=[f"Is '{correction.get('corrected')}' now the correct value? Has the original document been updated?"],
                    priority=4,
                    category='contradiction'
                ))

            # Create gaps from missing references
            for ref in result.get('references', []):
                if not ref.get('exists_in_docs', True):
                    self.gaps.append(DetectedGap(
                        gap_type='reference_missing',
                        title=f"Missing reference: {ref.get('name', 'Unknown')}",
                        description=f"Document references '{ref.get('name')}' ({ref.get('type', 'document')}) but it was not found in the knowledge base.",
                        evidence=[f"Referenced in: {docs[0]['title']}"],
                        source_docs=[d['id'] for d in docs],
                        questions=[f"Where is the {ref.get('type', 'document')} for '{ref.get('name')}'? Does it exist?"],
                        priority=3,
                        category='reference_missing'
                    ))

            # Create gaps from tribal knowledge
            for tip in result.get('tribal_knowledge', []):
                self.gaps.append(DetectedGap(
                    gap_type='tribal_knowledge',
                    title=f"Tribal knowledge: {tip.get('tip', '')[:50]}...",
                    description=f"Informal tip found: {tip.get('tip')}\nContext: {tip.get('context', 'Not specified')}",
                    evidence=[f"Found in: {docs[0]['title']}"],
                    source_docs=[d['id'] for d in docs],
                    questions=["Has this tip been added to the official protocol?", "Is this still accurate?"],
                    priority=2,
                    category='tribal_knowledge'
                ))

        except Exception as e:
            logger.error(f"[ResearchGapDetector] Error extracting from batch: {e}")

    def _phase2_cross_source(self):
        """Phase 2: Find contradictions and gaps across sources"""

        # Build doc_id -> title map for including document names
        doc_id_to_title = {doc['id']: doc['title'] for doc in self.documents}

        # Find entities mentioned in multiple documents with different values
        for entity_name, mentions in self.entities.items():
            if len(mentions) < 2:
                continue

            # Check for value contradictions
            values = [m.get('value') for m in mentions if m.get('value')]
            unique_values = list(set(values))

            if len(unique_values) > 1:
                # Get document IDs and names involved
                involved_doc_ids = list(set([doc_id for m in mentions for doc_id in m.get('doc_ids', [])]))
                involved_doc_names = [doc_id_to_title.get(did, 'Unknown')[:30] for did in involved_doc_ids[:3]]
                docs_str = " vs ".join(involved_doc_names)

                self.gaps.append(DetectedGap(
                    gap_type='contradiction',
                    title=f"[CONFLICT: {docs_str}] {entity_name} has different values",
                    description=f"'{entity_name}' has conflicting values:\n" +
                               "\n".join([f"• '{v}'" for v in unique_values]) +
                               f"\n\nDocuments involved: {', '.join(involved_doc_names)}",
                    evidence=[f"Value '{v}' found in: {', '.join(involved_doc_names)}" for v in unique_values],
                    source_docs=involved_doc_ids,
                    questions=[f"What is the correct value for {entity_name}?",
                              f"Which document ({docs_str}) has the right value?"],
                    priority=4,
                    category='contradiction'
                ))

        # Find unanswered questions
        for q in self.questions:
            if not q.has_answer:
                self.gaps.append(DetectedGap(
                    gap_type='question_unanswered',
                    title=f"Unanswered question: {q.question_text[:50]}...",
                    description=f"Question found in {q.doc_type}: {q.question_text}",
                    evidence=[f"Asked in document: {q.doc_id}"],
                    source_docs=[q.doc_id],
                    questions=[q.question_text, "Who can answer this?", "Where should the answer be documented?"],
                    priority=3,
                    category='question_unanswered'
                ))

    def _phase3_source_specific(self):
        """Phase 3: Run source-specific gap analysis"""

        # Group documents by type
        by_type = defaultdict(list)
        for doc in self.documents:
            by_type[doc['doc_type']].append(doc)

        # Analyze protocols specifically
        if by_type.get('protocol'):
            self._analyze_protocols(by_type['protocol'])

        # Analyze research papers
        if by_type.get('paper'):
            self._analyze_papers(by_type['paper'])

        # Analyze presentations
        if by_type.get('presentation'):
            self._analyze_presentations(by_type['presentation'])

        # Analyze code/GitHub
        if by_type.get('github'):
            self._analyze_code(by_type['github'])

        # Analyze chat/Slack for person-locked knowledge
        if by_type.get('slack') or by_type.get('email'):
            self._analyze_communications(by_type.get('slack', []) + by_type.get('email', []))

        # Analyze documents typed as 'other' with generic research analysis
        if by_type.get('other'):
            self._analyze_other_research_docs(by_type['other'])

    def _analyze_protocols(self, protocols: List[Dict]):
        """Analyze protocols for completeness"""

        for protocol in protocols[:10]:  # Limit to avoid API overload
            prompt = f"""You are analyzing a research lab protocol to find SPECIFIC missing information that would prevent someone from reproducing the experiment.

PROTOCOL: {protocol['title']}
CONTENT:
{protocol['content'][:20000]}

Find SPECIFIC gaps - not generic questions. For each issue you find, quote the EXACT problematic text.

LOOK FOR:

1. VAGUE NUMBERS - Find exact quotes like:
   - "centrifuge at max speed" → Ask: "What RPM or g-force? Different centrifuges have different max speeds"
   - "incubate overnight" → Ask: "How many hours exactly? 12h? 16h? 18h?"
   - "add some buffer" → Ask: "What volume exactly?"
   - "room temperature" → Ask: "What temperature range? 20-25°C?"
   - "briefly vortex" → Ask: "How many seconds?"

2. MISSING REAGENT INFO - Find reagents without:
   - Vendor/catalog number → Ask: "What is the catalog number for [reagent]?"
   - Lot number (for antibodies) → Ask: "What lot number? Antibodies vary between batches"
   - Storage location → Ask: "Where is [reagent] stored in the lab?"
   - Preparation method → Ask: "How do you prepare [reagent] working solution?"

3. EQUIPMENT WITHOUT SETTINGS - Find equipment mentions without:
   - Speed/RPM → Ask: "What speed setting for [equipment]?"
   - Temperature → Ask: "What temperature for [equipment]?"
   - Duration → Ask: "How long to run [equipment]?"

4. NO TROUBLESHOOTING - Find critical steps with no error guidance:
   - Ask: "What do you do if [step] fails?"
   - Ask: "How do you know if [step] worked correctly?"

IMPORTANT:
- Quote the EXACT text from the protocol that has the problem
- Ask SPECIFIC questions, not generic ones
- Each question should reference the actual content

BAD example (too generic): "What are the standard procedures?"
GOOD example (specific): "The protocol says 'centrifuge at max speed' - what RPM should be used?"

Respond in JSON:
{{
    "gaps": [
        {{
            "type": "vague_parameter|missing_reagent_info|equipment_settings|troubleshooting",
            "problematic_text": "EXACT quote from protocol",
            "problem": "specific issue with this text",
            "question": "specific question referencing the actual text"
        }}
    ]
}}
"""

            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a research reproducibility expert. Identify gaps in lab protocols."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=3000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                type_to_category = {
                    'vague_parameter': 'protocol_incomplete',
                    'missing_detail': 'protocol_incomplete',
                    'newcomer_confusion': 'protocol_incomplete',
                    'troubleshooting': 'troubleshooting_missing',
                    'reproducibility': 'reproducibility_risk',
                    'statistical': 'statistical_unclear'
                }

                for gap in result.get('gaps', []):
                    # Include document name directly in the title
                    doc_name = protocol['title'][:50]
                    question = gap.get('question', 'Please clarify this section')

                    self.gaps.append(DetectedGap(
                        gap_type=gap.get('type', 'missing_detail'),
                        title=f"[{doc_name}] {question[:100]}",
                        description=f"Document: {protocol['title']}\n\nProblematic text: \"{gap.get('problematic_text', 'N/A')}\"\n\nIssue: {gap.get('problem', '')}",
                        evidence=[f"Found in: {protocol['title']}"],
                        source_docs=[protocol['id']],
                        questions=[question],
                        priority=3,
                        category=type_to_category.get(gap.get('type'), 'protocol_incomplete')
                    ))

            except Exception as e:
                logger.error(f"[ResearchGapDetector] Error analyzing protocol: {e}")

    def _analyze_code(self, code_docs: List[Dict]):
        """Analyze code for documentation gaps"""

        for doc in code_docs[:5]:
            prompt = f"""Analyze this code/repository documentation for gaps.

CONTENT:
{doc['content'][:15000]}

Check for:
1. Missing README or documentation
2. Functions/methods without explanations
3. Data processing without methodology description
4. Dependencies not documented
5. Usage examples missing

Respond in JSON:
{{
    "gaps": [
        {{"type": "...", "description": "...", "question": "..."}}
    ]
}}
"""

            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a code documentation expert."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                for gap in result.get('gaps', []):
                    doc_name = doc['title'][:50]
                    question = gap.get('question', 'Please document this')

                    self.gaps.append(DetectedGap(
                        gap_type='code_undocumented',
                        title=f"[{doc_name}] {question[:100]}",
                        description=f"Document: {doc['title']}\n\n{gap.get('description', '')}",
                        evidence=[f"Found in: {doc['title']}"],
                        source_docs=[doc['id']],
                        questions=[question],
                        priority=2,
                        category='code_undocumented'
                    ))

            except Exception as e:
                logger.error(f"[ResearchGapDetector] Error analyzing code: {e}")

    def _analyze_communications(self, comm_docs: List[Dict]):
        """Analyze Slack/email for person-locked knowledge"""

        # Combine communications for analysis
        combined = "\n\n".join([f"=== {d['title']} ===\n{d['content'][:5000]}" for d in comm_docs[:20]])

        if not combined:
            return

        prompt = f"""Analyze these lab communications (Slack/email) for knowledge management issues.

COMMUNICATIONS:
{combined[:30000]}

Find:
1. PERSON-LOCKED KNOWLEDGE: "Ask [person]", "[person] knows", expertise not documented
2. INFORMAL CORRECTIONS: "Actually, use X not Y", corrections not in official docs
3. REPEATED QUESTIONS: Same questions asked multiple times (indicates missing documentation)
4. UNDOCUMENTED DECISIONS: Decisions made in chat but not recorded formally

Respond in JSON:
{{
    "person_locked": [
        {{"person": "...", "knowledge_area": "...", "evidence": "quote from chat"}}
    ],
    "informal_corrections": [
        {{"correction": "...", "evidence": "..."}}
    ],
    "repeated_questions": [
        {{"question_topic": "...", "times_asked": N}}
    ],
    "undocumented_decisions": [
        {{"decision": "...", "evidence": "..."}}
    ]
}}
"""

        try:
            response = self.client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a knowledge management expert for research labs."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)

            # Person-locked knowledge
            for item in result.get('person_locked', []):
                self.gaps.append(DetectedGap(
                    gap_type='person_locked',
                    title=f"Person-locked knowledge: {item.get('person', 'Unknown')} - {item.get('knowledge_area', '')}",
                    description=f"{item.get('person', 'Someone')} appears to have undocumented expertise in: {item.get('knowledge_area', 'unspecified area')}\n\nEvidence: \"{item.get('evidence', 'N/A')}\"",
                    evidence=[item.get('evidence', 'Found in communications')],
                    source_docs=[d['id'] for d in comm_docs[:5]],
                    questions=[
                        f"Can {item.get('person', 'they')} document their knowledge about {item.get('knowledge_area', 'this topic')}?",
                        "What happens if this person is unavailable?",
                        "Where should this knowledge be documented?"
                    ],
                    priority=4,
                    category='person_locked'
                ))

            # Informal corrections
            for item in result.get('informal_corrections', []):
                self.gaps.append(DetectedGap(
                    gap_type='chat_not_documented',
                    title=f"Informal correction: {item.get('correction', '')[:50]}",
                    description=f"Correction found in chat but may not be in official documentation:\n\n{item.get('correction', '')}",
                    evidence=[item.get('evidence', 'Found in chat')],
                    source_docs=[d['id'] for d in comm_docs[:3]],
                    questions=["Has the official protocol been updated with this correction?", "Is this correction verified?"],
                    priority=4,
                    category='chat_not_documented'
                ))

            # Repeated questions
            for item in result.get('repeated_questions', []):
                if item.get('times_asked', 0) >= 2:
                    self.gaps.append(DetectedGap(
                        gap_type='question_unanswered',
                        title=f"Frequently asked: {item.get('question_topic', '')}",
                        description=f"This question/topic has been asked ~{item.get('times_asked', 'multiple')} times, suggesting missing documentation.",
                        evidence=["Found multiple times in communications"],
                        source_docs=[d['id'] for d in comm_docs[:3]],
                        questions=[f"Where should the answer to '{item.get('question_topic', 'this')}' be documented?"],
                        priority=3,
                        category='protocol_incomplete'
                    ))

        except Exception as e:
            logger.error(f"[ResearchGapDetector] Error analyzing communications: {e}")

    def _analyze_papers(self, papers: List[Dict]):
        """Analyze research papers for reproducibility and methodology gaps"""

        for paper in papers[:10]:
            prompt = f"""You are analyzing a research paper or manuscript to find SPECIFIC information gaps that would prevent reproducibility or understanding.

PAPER: {paper['title']}
CONTENT:
{paper['content'][:20000]}

Find SPECIFIC gaps in this paper. For each issue, quote the EXACT problematic text.

LOOK FOR:

1. METHODS LACKING DETAIL:
   - Vague descriptions like "standard protocol" → Ask: "What specific protocol was used? Citation or steps?"
   - Missing concentrations, volumes, times
   - Unreferenced techniques → Ask: "What is the citation for this method?"

2. MISSING REAGENT DETAILS:
   - Antibodies without clone/lot numbers → Ask: "What antibody clone was used?"
   - Chemicals without vendors → Ask: "What vendor and catalog number?"
   - Custom reagents without preparation → Ask: "How was this prepared?"

3. STATISTICAL GAPS:
   - "Significant" without p-values → Ask: "What was the exact p-value?"
   - Missing n numbers → Ask: "What was the sample size?"
   - Unclear statistical tests → Ask: "Which statistical test was used?"

4. DATA GAPS:
   - "Data not shown" → Ask: "Where can this data be accessed?"
   - Missing raw data availability → Ask: "Is raw data available?"

IMPORTANT: Quote the EXACT problematic text and ask SPECIFIC questions about it.

BAD: "Are methods complete?"
GOOD: "The paper says 'cells were lysed using standard buffer' - what is the buffer composition?"

Respond in JSON:
{{
    "gaps": [
        {{
            "type": "methods_incomplete|reagent_missing|statistical_gap|data_gap",
            "problematic_text": "EXACT quote from paper",
            "problem": "specific issue",
            "question": "specific question about the quoted text"
        }}
    ]
}}
"""

            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a peer reviewer identifying reproducibility issues in research papers."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=3000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                for gap in result.get('gaps', []):
                    doc_name = paper['title'][:50]
                    question = gap.get('question', 'Please provide more detail')

                    self.gaps.append(DetectedGap(
                        gap_type=gap.get('type', 'methods_incomplete'),
                        title=f"[{doc_name}] {question[:100]}",
                        description=f"Document: {paper['title']}\n\nProblematic text: \"{gap.get('problematic_text', 'N/A')}\"\n\nIssue: {gap.get('problem', '')}",
                        evidence=[f"Found in: {paper['title']}"],
                        source_docs=[paper['id']],
                        questions=[question],
                        priority=3,
                        category='reproducibility_risk'
                    ))

            except Exception as e:
                logger.error(f"[ResearchGapDetector] Error analyzing paper: {e}")

    def _analyze_presentations(self, presentations: List[Dict]):
        """Analyze presentations for undocumented claims and missing context"""

        for pres in presentations[:5]:
            prompt = f"""Analyze this presentation/slides for knowledge gaps.

PRESENTATION: {pres['title']}
CONTENT:
{pres['content'][:15000]}

Presentations often contain claims, data, and decisions that aren't documented elsewhere.

Find:
1. CLAIMS WITHOUT BACKING: Results or conclusions that need supporting documents
2. DATA WITHOUT SOURCE: Charts, numbers, or statistics without clear source
3. DECISIONS MENTIONED: Strategic or technical decisions that should be documented
4. ACTION ITEMS: Tasks or next steps mentioned but not tracked
5. REFERENCES TO MISSING DOCS: "See the protocol", "as per the report" without links

For each issue, quote the relevant text and ask a specific question.

Respond in JSON:
{{
    "gaps": [
        {{
            "type": "unsourced_claim|missing_reference|undocumented_decision|action_item",
            "problematic_text": "quote from presentation",
            "question": "specific question"
        }}
    ]
}}
"""

            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a knowledge management expert analyzing presentations for documentation gaps."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                for gap in result.get('gaps', []):
                    doc_name = pres['title'][:50]
                    question = gap.get('question', 'Where is this documented?')

                    self.gaps.append(DetectedGap(
                        gap_type=gap.get('type', 'unsourced_claim'),
                        title=f"[{doc_name}] {question[:100]}",
                        description=f"Document: {pres['title']}\n\nText: \"{gap.get('problematic_text', 'N/A')}\"",
                        evidence=[f"Found in presentation: {pres['title']}"],
                        source_docs=[pres['id']],
                        questions=[question],
                        priority=2,
                        category='reference_missing'
                    ))

            except Exception as e:
                logger.error(f"[ResearchGapDetector] Error analyzing presentation: {e}")

    def _analyze_other_research_docs(self, docs: List[Dict]):
        """Analyze documents that couldn't be categorized using general research analysis"""

        for doc in docs[:10]:
            prompt = f"""Analyze this research-related document for knowledge gaps.

DOCUMENT: {doc['title']}
CONTENT:
{doc['content'][:15000]}

Even though this document type is unclear, look for common research knowledge gaps:

1. VAGUE TECHNICAL DETAILS: Numbers without units, "approximately" without specifics
2. UNDEFINED TERMS: Acronyms, jargon, or techniques that aren't explained
3. MISSING CONTEXT: References to other work, people, or systems without explanation
4. INCOMPLETE PROCEDURES: Steps mentioned but not fully described
5. UNANSWERED QUESTIONS: Questions posed but not answered
6. PERSON DEPENDENCIES: "Ask John", "Sarah handles this"

For each issue, quote the exact text and ask a specific, actionable question.

Respond in JSON:
{{
    "gaps": [
        {{
            "type": "vague_detail|undefined_term|missing_context|incomplete_procedure|unanswered|person_dependency",
            "problematic_text": "EXACT quote",
            "question": "specific question about this text"
        }}
    ]
}}
"""

            try:
                response = self.client.chat_completion(
                    messages=[
                        {"role": "system", "content": "You are a research documentation expert identifying knowledge gaps."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=2000,
                    response_format={"type": "json_object"}
                )

                result = json.loads(response.choices[0].message.content)

                for gap in result.get('gaps', []):
                    doc_name = doc['title'][:50]
                    question = gap.get('question', 'Please clarify this')

                    category_map = {
                        'vague_detail': 'protocol_incomplete',
                        'undefined_term': 'protocol_incomplete',
                        'missing_context': 'reference_missing',
                        'incomplete_procedure': 'protocol_incomplete',
                        'unanswered': 'question_unanswered',
                        'person_dependency': 'person_locked'
                    }

                    self.gaps.append(DetectedGap(
                        gap_type=gap.get('type', 'missing_context'),
                        title=f"[{doc_name}] {question[:100]}",
                        description=f"Document: {doc['title']}\n\nText: \"{gap.get('problematic_text', 'N/A')}\"",
                        evidence=[f"Found in: {doc['title']}"],
                        source_docs=[doc['id']],
                        questions=[question],
                        priority=2,
                        category=category_map.get(gap.get('type'), 'protocol_incomplete')
                    ))

            except Exception as e:
                logger.error(f"[ResearchGapDetector] Error analyzing document: {e}")

    def _phase4_knowledge_graph(self):
        """Phase 4: Identify gaps in the knowledge graph"""

        # Find people mentioned frequently but without documented expertise
        people_mentions = defaultdict(int)
        for entity_name, mentions in self.entities.items():
            for m in mentions:
                if m.get('type') == 'person':
                    people_mentions[entity_name] += 1

        # Find methods/techniques mentioned but no protocol exists
        methods_with_docs = defaultdict(set)  # method_name -> set of doc_ids
        protocols_titles = set()
        doc_id_to_title = {doc['id']: doc['title'] for doc in self.documents}

        for doc in self.documents:
            if doc['doc_type'] == 'protocol':
                protocols_titles.add(doc['title'].lower())

        for entity_name, mentions in self.entities.items():
            for m in mentions:
                if m.get('type') == 'method':
                    for doc_id in m.get('doc_ids', []):
                        methods_with_docs[entity_name].add(doc_id)

        # Check if methods have corresponding protocols
        for method, doc_ids in methods_with_docs.items():
            has_protocol = any(method.lower() in title for title in protocols_titles)
            if not has_protocol:
                # Get document names that mention this method
                doc_names = [doc_id_to_title.get(did, 'Unknown')[:25] for did in list(doc_ids)[:3]]
                docs_str = ", ".join(doc_names)

                self.gaps.append(DetectedGap(
                    gap_type='method_no_protocol',
                    title=f"[Missing Protocol] {method} (mentioned in: {docs_str})",
                    description=f"The method '{method}' is mentioned in these documents but no protocol exists:\n" +
                               "\n".join([f"• {name}" for name in doc_names]),
                    evidence=[f"Method '{method}' referenced in: {docs_str}"],
                    source_docs=list(doc_ids),
                    questions=[f"Is there a protocol for '{method}'?",
                              f"Which document ({docs_str}) should contain the protocol?"],
                    priority=3,
                    category='method_no_protocol'
                ))

    def _deduplicate_gaps(self):
        """Remove duplicate or very similar gaps"""
        seen_titles = set()
        unique_gaps = []

        for gap in self.gaps:
            title_key = gap.title.lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_gaps.append(gap)

        self.gaps = unique_gaps

    def _prioritize_gaps(self):
        """Sort gaps by priority"""
        # Priority order: contradiction > person_locked > protocol > others
        priority_boost = {
            'contradiction': 2,
            'person_locked': 2,
            'chat_not_documented': 1,
            'reproducibility_risk': 1,
            'protocol_incomplete': 0,
            'question_unanswered': 0,
            'reference_missing': 0,
            'tribal_knowledge': -1,
            'code_undocumented': -1
        }

        for gap in self.gaps:
            gap.priority = min(5, max(1, gap.priority + priority_boost.get(gap.category, 0)))

        self.gaps.sort(key=lambda g: (-g.priority, g.category))

    def _count_by_category(self) -> Dict[str, int]:
        """Count gaps by category"""
        counts = defaultdict(int)
        for gap in self.gaps:
            counts[gap.category] += 1
        return dict(counts)

    def _gap_to_dict(self, gap: DetectedGap) -> Dict:
        """Convert gap to dictionary"""
        return {
            'gap_type': gap.gap_type,
            'title': gap.title,
            'description': gap.description,
            'evidence': gap.evidence,
            'source_docs': gap.source_docs,
            'questions': gap.questions,
            'priority': gap.priority,
            'category': gap.category
        }

    def to_knowledge_gaps(self, result: Dict, project_id: Optional[str] = None) -> List[Dict]:
        """Convert analysis result to knowledge gap format for database"""
        gaps_data = []

        # Build a map of doc_id -> title from our documents
        doc_id_to_title = {doc['id']: doc['title'] for doc in self.documents}

        for gap_dict in result.get('gaps', []):
            # Get source document IDs and resolve to titles
            source_doc_ids = gap_dict.get('source_docs', [])
            source_documents = []
            for doc_id in source_doc_ids:
                title = doc_id_to_title.get(doc_id, 'Unknown Document')
                source_documents.append({'id': doc_id, 'title': title})

            gaps_data.append({
                'title': gap_dict.get('title', 'Unknown Gap')[:200],
                'description': gap_dict.get('description', '')[:2000],
                'category': gap_dict.get('category', 'protocol_incomplete'),
                'priority': gap_dict.get('priority', 3),
                'questions': [
                    {'text': q, 'answered': False}
                    for q in gap_dict.get('questions', [])[:10]
                ],
                'context': {
                    'gap_type': gap_dict.get('gap_type'),
                    'evidence': gap_dict.get('evidence', []),
                    'source_docs': source_doc_ids,
                    'source_documents': source_documents,  # Include titles directly
                    'analysis_type': 'research_multi_source'
                }
            })

        return gaps_data


# Singleton instance
_detector_instance = None

def get_research_gap_detector() -> ResearchGapDetector:
    """Get or create the research gap detector instance"""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = ResearchGapDetector()
    return _detector_instance
