"""
Stakeholder Graph Module
Extracts people, roles, expertise, and relationships from documents.
Enables "who knows what" queries for knowledge transfer.
"""

import re
import json
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass, field
from collections import defaultdict
import pickle
from pathlib import Path


@dataclass
class Person:
    """Represents a person in the organization"""
    name: str
    normalized_name: str  # Lowercase, standardized
    roles: Set[str] = field(default_factory=set)
    expertise: Set[str] = field(default_factory=set)
    projects: Set[str] = field(default_factory=set)
    documents: Set[str] = field(default_factory=set)  # Doc IDs where mentioned
    mentions: int = 0
    email: Optional[str] = None
    department: Optional[str] = None
    relationships: Dict[str, str] = field(default_factory=dict)  # person_name -> relationship_type


@dataclass
class Project:
    """Represents a project or initiative"""
    name: str
    normalized_name: str
    members: Set[str] = field(default_factory=set)  # Person names
    documents: Set[str] = field(default_factory=set)
    topics: Set[str] = field(default_factory=set)
    status: Optional[str] = None
    client: Optional[str] = None


class StakeholderGraph:
    """
    Builds and queries a graph of people, their expertise, and relationships.
    """

    # Role patterns
    ROLE_PATTERNS = [
        (r'\b(?:CEO|CFO|CTO|COO|CMO|CIO|CHRO)\b', 'C-Suite'),
        (r'\b(?:President|Vice President|VP|SVP|EVP)\b', 'Executive'),
        (r'\b(?:Director|Senior Director|Managing Director)\b', 'Director'),
        (r'\b(?:Manager|Senior Manager|Project Manager|PM)\b', 'Manager'),
        (r'\b(?:Lead|Team Lead|Tech Lead)\b', 'Lead'),
        (r'\b(?:Consultant|Senior Consultant|Associate Consultant)\b', 'Consultant'),
        (r'\b(?:Analyst|Senior Analyst|Business Analyst)\b', 'Analyst'),
        (r'\b(?:Engineer|Software Engineer|Data Engineer)\b', 'Engineer'),
        (r'\b(?:Founder|Co-Founder)\b', 'Founder'),
        (r'\b(?:Partner|Managing Partner)\b', 'Partner'),
        (r'\b(?:Intern|Fellow)\b', 'Intern'),
        (r'\b(?:Professor|Dr\.|PhD)\b', 'Academic'),
    ]

    # Expertise domain patterns
    EXPERTISE_PATTERNS = [
        (r'\b(?:financial analysis|valuation|DCF|M&A|mergers)\b', 'Finance'),
        (r'\b(?:marketing|brand|customer acquisition|GTM|go-to-market)\b', 'Marketing'),
        (r'\b(?:healthcare|medical|clinical|patient|NICU|hospital)\b', 'Healthcare'),
        (r'\b(?:technology|software|engineering|data|ML|AI)\b', 'Technology'),
        (r'\b(?:strategy|consulting|market analysis|competitive)\b', 'Strategy'),
        (r'\b(?:operations|supply chain|logistics|process)\b', 'Operations'),
        (r'\b(?:sales|revenue|pipeline|deals)\b', 'Sales'),
        (r'\b(?:legal|compliance|regulatory|FDA)\b', 'Legal/Regulatory'),
        (r'\b(?:HR|human resources|recruiting|talent)\b', 'Human Resources'),
        (r'\b(?:product|product management|roadmap|features)\b', 'Product'),
    ]

    # Name patterns (captures common name formats)
    NAME_PATTERNS = [
        r'\b([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # John A. Smith
        r'(?:by|from|authored by|prepared by|team:?)[\s:]+([A-Z][a-z]+\s+[A-Z][a-z]+)',  # by John Smith
        r'(?:contact|email|reach):?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)',  # contact John Smith
    ]

    # Common non-name words to filter
    NON_NAME_WORDS = {
        # Common section headers and document terms
        'Executive', 'Summary', 'Financial', 'Analysis', 'Market', 'Research',
        'Project', 'Business', 'Case', 'Study', 'Report', 'Annual', 'Quarterly',
        'Health', 'Care', 'Medical', 'Clinical', 'Patient', 'Insurance',
        'The', 'This', 'That', 'These', 'Those', 'With', 'From', 'Into',
        'Chapter', 'Section', 'Part', 'Slide', 'Table', 'Figure', 'Chart',
        'January', 'February', 'March', 'April', 'May', 'June', 'July',
        'August', 'September', 'October', 'November', 'December',
        'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday',
        'United', 'States', 'America', 'California', 'Angeles', 'York', 'Boston',
        'North', 'South', 'East', 'West', 'Central', 'Pacific', 'Atlantic',
        'Thank', 'You', 'Dear', 'Hello', 'Hi', 'Best', 'Regards', 'Sincerely',
        # Document section headers that get misidentified as names
        'Important', 'Dates', 'Action', 'Items', 'Main', 'Topics', 'Key', 'Entities',
        'Problem', 'Statement', 'Current', 'State', 'Next', 'Steps', 'Team', 'Members',
        'Data', 'Science', 'Cost', 'Savings', 'Human', 'Resources', 'Step', 'Down',
        'Revenue', 'Growth', 'Organization', 'Structure', 'Additional', 'Considerations',
        'Data', 'Collection', 'Request', 'Success', 'Metrics', 'Contribution', 'Margin',
        'Net', 'Present', 'Value', 'Profit', 'Turning', 'Away', 'Critical', 'Vision',
        'General', 'Pediatric', 'Pediatrics', 'Beds', 'Fetal', 'Diagnostics', 'Unit',
        'Neonatal', 'Patients', 'Cardiac', 'Operational', 'Efficiency', 'Surgical',
        'Robotics', 'Total', 'Number', 'Transfer', 'Hospital', 'Administration',
        'Confidential', 'Information', 'Screening', 'Guidelines', 'Honor', 'Roll',
        'Disclosure', 'Agreement', 'Healthcare', 'Consulting', 'Recommended', 'Strategies',
        'Lost', 'Opportunity', 'Home', 'Accuracy', 'Immediate', 'Life', 'Threatening',
        'Respiratory', 'Distress', 'Technological', 'Acquisitions', 'Administrative',
        'Equipment', 'Nursing', 'Greater', 'Avoidance', 'Labor', 'Act', 'Services',
        'Performed', 'Evaluation', 'Period', 'Sponsor', 'Creation', 'Placenta',
        'Accreta', 'Facilitating', 'Access', 'Qualitative', 'Measurements', 'American',
        'Committee', 'Opinion', 'Assisted', 'Systems', 'Discharge', 'Date', 'Rey',
        'Introduction', 'Overview', 'Background', 'Methodology', 'Conclusion', 'Results',
        'Appendix', 'References', 'Acknowledgments', 'Abstract', 'Contents', 'Index',
        'Competitive', 'Landscape', 'Target', 'Audience', 'Value', 'Proposition',
        'Charter', 'Timeline', 'Deliverables', 'Milestones', 'Objectives', 'Goals',
        'Scope', 'Requirements', 'Assumptions', 'Constraints', 'Risks', 'Issues',
        'Mexico', 'City', 'National', 'Agricultural', 'Statistics', 'Census', 'Bureau',
        'Mind', 'My',
        # Additional non-person terms
        'Countries', 'Producing', 'Global', 'Production', 'Blueberry', 'Blueberries',
        'Federal', 'Regulations', 'Artificial', 'Intelligence', 'Kaiser', 'Permanente',
        'Vinci', 'Cedars', 'Sinai', 'Providence', 'UCLA', 'Stanford', 'Harvard', 'MIT',
        'Google', 'Amazon', 'Apple', 'Microsoft', 'Facebook', 'Meta', 'Netflix', 'Tesla',
        'Boeing', 'Adidas', 'Nike', 'Amgen', 'Pfizer', 'Johnson', 'McKinsey', 'Bain', 'BCG',
        'Deloitte', 'Accenture', 'KPMG', 'PwC', 'Goldman', 'Sachs', 'Morgan', 'Stanley',
        'Venture', 'Ventures', 'Capital', 'Holdings', 'Corporation', 'Inc', 'LLC', 'Ltd',
        'Foundation', 'Institute', 'University', 'College', 'School', 'Academy', 'Center',
        'Association', 'Society', 'Council', 'Board', 'Committee', 'Commission', 'Agency',
    }

    # Known actual person names to always include
    KNOWN_NAMES = {
        'rishit jain', 'eric yang', 'badri mishra', 'badri vinayak mishra',
        'pranav reddy', 'stewart fang', 'alan tran', 'melaney stricklin',
        'danny zhu', 'rohit guha', 'shawn wang', 'gil travish',
    }

    # Common phrases that are NOT names (multi-word filters)
    NOT_NAME_PHRASES = {
        'obstetrics emergency', 'emergency department', 'row labels', 'governing law',
        'southern hemisphere', 'metric tons', 'service noncitrus', 'gen ped',
        'pretoria chile', 'ucla health', 'los angeles', 'new york', 'san francisco',
        'united states', 'north america', 'south america', 'latin america',
        'case study', 'market analysis', 'financial model', 'business plan',
        'executive summary', 'table of contents', 'appendix a', 'appendix b',
        'figure 1', 'figure 2', 'table 1', 'table 2', 'page 1', 'page 2',
        'section 1', 'section 2', 'part 1', 'part 2', 'chapter 1', 'chapter 2',
        'privacy policy', 'terms of service', 'confidentiality agreement',
        'non disclosure', 'intellectual property', 'governing law',
        'neonatal intensive', 'intensive care', 'labor act', 'latin america',
        'countries producing', 'global production', 'global blueberry', 'blueberry production',
        'federal regulations', 'artificial intelligence', 'kaiser permanente', 'da vinci',
        'cedars sinai', 'machine learning', 'deep learning', 'natural language',
    }

    def __init__(self):
        self.people: Dict[str, Person] = {}  # normalized_name -> Person
        self.projects: Dict[str, Project] = {}  # normalized_name -> Project
        self.document_people: Dict[str, Set[str]] = defaultdict(set)  # doc_id -> set of person names
        self.expertise_people: Dict[str, Set[str]] = defaultdict(set)  # expertise -> set of person names

    def normalize_name(self, name: str) -> str:
        """Normalize a name for consistent matching"""
        # Remove extra whitespace
        name = ' '.join(name.split())
        # Lowercase for comparison
        return name.lower().strip()

    def is_valid_name(self, name: str) -> bool:
        """Check if extracted text is likely a real name"""
        normalized = self.normalize_name(name)

        # Check known names first - always valid
        if normalized in self.KNOWN_NAMES:
            return True

        # Check if matches NOT_NAME_PHRASES
        for phrase in self.NOT_NAME_PHRASES:
            if phrase in normalized:
                return False

        parts = name.split()

        # Must have at least 2 parts (first and last name)
        if len(parts) < 2:
            return False

        # Check for non-name words - any part matching means it's not a name
        for part in parts:
            if part in self.NON_NAME_WORDS:
                return False

        # First part should start with uppercase
        if not parts[0][0].isupper():
            return False

        # Names shouldn't be too long
        if len(parts) > 4:
            return False

        # Each part should be reasonable length
        for part in parts:
            if len(part) > 15:
                return False

        # Additional filter: name parts should look like name parts
        # (avoid things like "Healthcare Consulting", "Data Science")
        # Real names typically have first name and last name patterns
        # Filter out phrases where both words are common English words
        common_words = {
            'healthcare', 'consulting', 'data', 'science', 'cost', 'savings',
            'human', 'resources', 'revenue', 'growth', 'market', 'research',
            'financial', 'analysis', 'project', 'management', 'business',
            'development', 'operations', 'strategy', 'technology', 'product',
            'service', 'customer', 'sales', 'marketing', 'engineering',
            'emergency', 'department', 'intensive', 'care', 'unit', 'hospital',
            'row', 'labels', 'governing', 'law', 'southern', 'hemisphere',
            'metric', 'tons', 'noncitrus', 'fruits', 'pretoria', 'chile',
            'gen', 'ped', 'obstetrics',
        }
        lower_parts = [p.lower() for p in parts]
        if all(p in common_words for p in lower_parts):
            return False

        # Filter single common words that slip through
        single_common = {'obstetrics', 'pediatrics', 'neonatal', 'cardiology', 'oncology'}
        if any(p.lower() in single_common for p in parts):
            return False

        return True

    def extract_names(self, text: str) -> List[str]:
        """Extract person names from text"""
        names = set()

        for pattern in self.NAME_PATTERNS:
            matches = re.findall(pattern, text)
            for match in matches:
                if self.is_valid_name(match):
                    names.add(match)

        return list(names)

    def extract_emails(self, text: str) -> Dict[str, str]:
        """Extract email addresses and try to associate with names"""
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        emails = re.findall(email_pattern, text)

        name_emails = {}
        for email in emails:
            # Try to extract name from email
            local_part = email.split('@')[0]
            # Check for firstname.lastname pattern
            if '.' in local_part:
                parts = local_part.split('.')
                if len(parts) == 2:
                    name = f"{parts[0].title()} {parts[1].title()}"
                    if self.is_valid_name(name):
                        name_emails[name] = email

        return name_emails

    def extract_roles(self, text: str, person_name: str) -> Set[str]:
        """Extract roles associated with a person"""
        roles = set()

        # Look for role patterns near the person's name
        name_pattern = re.escape(person_name)
        context_pattern = rf'.{{0,100}}{name_pattern}.{{0,100}}'

        contexts = re.findall(context_pattern, text, re.IGNORECASE)

        for context in contexts:
            for pattern, role in self.ROLE_PATTERNS:
                if re.search(pattern, context, re.IGNORECASE):
                    roles.add(role)

        return roles

    def extract_expertise(self, text: str, person_name: str) -> Set[str]:
        """Extract expertise domains for a person"""
        expertise = set()

        # Look for expertise patterns near the person's name
        name_pattern = re.escape(person_name)
        context_pattern = rf'.{{0,200}}{name_pattern}.{{0,200}}'

        contexts = re.findall(context_pattern, text, re.IGNORECASE)

        for context in contexts:
            for pattern, domain in self.EXPERTISE_PATTERNS:
                if re.search(pattern, context, re.IGNORECASE):
                    expertise.add(domain)

        return expertise

    def extract_project_from_doc(self, content: str, metadata: Dict) -> Optional[str]:
        """Try to identify the project name from document content/metadata"""
        # Check metadata first
        if 'project_name' in metadata:
            return metadata['project_name']

        file_name = metadata.get('file_name', '')

        # Common project name patterns
        project_patterns = [
            r'(?:Project|Case|Client):?\s+([A-Z][A-Za-z0-9\s&]+)',
            r'([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)\s+(?:Case Study|Analysis|Project)',
        ]

        for pattern in project_patterns:
            match = re.search(pattern, content[:2000])  # Check first part of doc
            if match:
                return match.group(1).strip()

        # Fall back to file name
        if file_name:
            # Remove extension and clean up
            name = Path(file_name).stem
            name = re.sub(r'[-_]', ' ', name)
            name = ' '.join(word.title() for word in name.split())
            return name

        return None

    def process_document(self, doc_id: str, content: str, metadata: Dict = None):
        """Process a document to extract stakeholder information"""
        if metadata is None:
            metadata = {}

        # Extract names
        names = self.extract_names(content)

        # Extract emails
        email_map = self.extract_emails(content)

        # Add email-derived names
        for name in email_map.keys():
            if name not in names:
                names.append(name)

        # Identify project
        project_name = self.extract_project_from_doc(content, metadata)

        # Process each person
        for name in names:
            normalized = self.normalize_name(name)

            # Create or update person
            if normalized not in self.people:
                self.people[normalized] = Person(
                    name=name,
                    normalized_name=normalized
                )

            person = self.people[normalized]
            person.mentions += 1
            person.documents.add(doc_id)

            # Extract and add roles
            roles = self.extract_roles(content, name)
            person.roles.update(roles)

            # Extract and add expertise
            expertise = self.extract_expertise(content, name)
            person.expertise.update(expertise)

            # Add email if found
            if name in email_map:
                person.email = email_map[name]

            # Add project association
            if project_name:
                person.projects.add(project_name)

            # Update expertise index
            for exp in expertise:
                self.expertise_people[exp].add(normalized)

            # Update document-people mapping
            self.document_people[doc_id].add(normalized)

        # Create/update project
        if project_name:
            normalized_project = self.normalize_name(project_name)
            if normalized_project not in self.projects:
                self.projects[normalized_project] = Project(
                    name=project_name,
                    normalized_name=normalized_project
                )

            project = self.projects[normalized_project]
            project.documents.add(doc_id)
            for name in names:
                project.members.add(self.normalize_name(name))

            # Extract topics from document
            for pattern, domain in self.EXPERTISE_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    project.topics.add(domain)

    def find_person(self, query: str) -> Optional[Person]:
        """Find a person by name (fuzzy match)"""
        normalized_query = self.normalize_name(query)

        # Exact match
        if normalized_query in self.people:
            return self.people[normalized_query]

        # Partial match
        for normalized, person in self.people.items():
            if normalized_query in normalized or normalized in normalized_query:
                return person

        # Last name match
        query_parts = normalized_query.split()
        for normalized, person in self.people.items():
            name_parts = normalized.split()
            if query_parts[-1] == name_parts[-1]:  # Last name matches
                return person

        return None

    def get_experts(self, domain: str) -> List[Person]:
        """Get people with expertise in a domain"""
        domain_lower = domain.lower()
        experts = []

        # Check expertise index
        for exp, people in self.expertise_people.items():
            if domain_lower in exp.lower():
                for person_name in people:
                    if person_name in self.people:
                        experts.append(self.people[person_name])

        return experts

    def get_project_team(self, project_name: str) -> List[Person]:
        """Get team members for a project"""
        normalized = self.normalize_name(project_name)

        # Try exact match
        if normalized in self.projects:
            project = self.projects[normalized]
            return [self.people[name] for name in project.members if name in self.people]

        # Partial match
        for proj_normalized, project in self.projects.items():
            if normalized in proj_normalized or proj_normalized in normalized:
                return [self.people[name] for name in project.members if name in self.people]

        return []

    def get_person_knowledge(self, person_name: str) -> Dict:
        """Get comprehensive knowledge about a person"""
        person = self.find_person(person_name)
        if not person:
            return {"error": f"Person '{person_name}' not found"}

        return {
            "name": person.name,
            "roles": list(person.roles),
            "expertise": list(person.expertise),
            "projects": list(person.projects),
            "documents": list(person.documents),
            "mentions": person.mentions,
            "email": person.email,
            "department": person.department
        }

    def answer_who_question(self, question: str) -> Dict:
        """Answer 'who' questions about people and expertise"""
        question_lower = question.lower()

        result = {
            "question": question,
            "answer_type": None,
            "results": []
        }

        # Who worked on [project]?
        project_match = re.search(r'who (?:worked on|was on|is on|handles?|managed?|led)\s+(.+?)(?:\?|$)', question_lower)
        if project_match:
            project_name = project_match.group(1).strip()
            team = self.get_project_team(project_name)
            result["answer_type"] = "project_team"
            result["project"] = project_name
            result["results"] = [self.get_person_knowledge(p.name) for p in team]
            return result

        # Who knows about [topic]? / Who is expert in [topic]?
        expertise_match = re.search(r'who (?:knows?|is expert|specializes?|has expertise)\s+(?:about|in|with)?\s*(.+?)(?:\?|$)', question_lower)
        if expertise_match:
            domain = expertise_match.group(1).strip()
            experts = self.get_experts(domain)
            result["answer_type"] = "domain_experts"
            result["domain"] = domain
            result["results"] = [self.get_person_knowledge(p.name) for p in experts]
            return result

        # Who is [name]?
        who_is_match = re.search(r'who is\s+(.+?)(?:\?|$)', question_lower)
        if who_is_match:
            name = who_is_match.group(1).strip()
            person = self.find_person(name)
            if person:
                result["answer_type"] = "person_info"
                result["results"] = [self.get_person_knowledge(person.name)]
            return result

        # Who should I contact about [topic]?
        contact_match = re.search(r'who (?:should i|can i|to) contact\s+(?:about|for|regarding)?\s*(.+?)(?:\?|$)', question_lower)
        if contact_match:
            topic = contact_match.group(1).strip()
            experts = self.get_experts(topic)
            result["answer_type"] = "contact_recommendation"
            result["topic"] = topic
            result["results"] = [self.get_person_knowledge(p.name) for p in experts[:3]]  # Top 3
            return result

        return result

    def get_stats(self) -> Dict:
        """Get statistics about the stakeholder graph"""
        return {
            "total_people": len(self.people),
            "total_projects": len(self.projects),
            "expertise_domains": list(self.expertise_people.keys()),
            "top_mentioned": sorted(
                [(p.name, p.mentions) for p in self.people.values()],
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }

    def to_dict(self) -> Dict:
        """Serialize graph to dictionary"""
        return {
            "people": {
                name: {
                    "name": p.name,
                    "normalized_name": p.normalized_name,
                    "roles": list(p.roles),
                    "expertise": list(p.expertise),
                    "projects": list(p.projects),
                    "documents": list(p.documents),
                    "mentions": p.mentions,
                    "email": p.email,
                    "department": p.department,
                    "relationships": p.relationships
                }
                for name, p in self.people.items()
            },
            "projects": {
                name: {
                    "name": p.name,
                    "normalized_name": p.normalized_name,
                    "members": list(p.members),
                    "documents": list(p.documents),
                    "topics": list(p.topics),
                    "status": p.status,
                    "client": p.client
                }
                for name, p in self.projects.items()
            },
            "expertise_people": {k: list(v) for k, v in self.expertise_people.items()},
            "document_people": {k: list(v) for k, v in self.document_people.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'StakeholderGraph':
        """Deserialize graph from dictionary"""
        graph = cls()

        # Load people
        for name, p_data in data.get("people", {}).items():
            person = Person(
                name=p_data["name"],
                normalized_name=p_data["normalized_name"],
                roles=set(p_data.get("roles", [])),
                expertise=set(p_data.get("expertise", [])),
                projects=set(p_data.get("projects", [])),
                documents=set(p_data.get("documents", [])),
                mentions=p_data.get("mentions", 0),
                email=p_data.get("email"),
                department=p_data.get("department"),
                relationships=p_data.get("relationships", {})
            )
            graph.people[name] = person

        # Load projects
        for name, p_data in data.get("projects", {}).items():
            project = Project(
                name=p_data["name"],
                normalized_name=p_data["normalized_name"],
                members=set(p_data.get("members", [])),
                documents=set(p_data.get("documents", [])),
                topics=set(p_data.get("topics", [])),
                status=p_data.get("status"),
                client=p_data.get("client")
            )
            graph.projects[name] = project

        # Load indices
        graph.expertise_people = defaultdict(set, {
            k: set(v) for k, v in data.get("expertise_people", {}).items()
        })
        graph.document_people = defaultdict(set, {
            k: set(v) for k, v in data.get("document_people", {}).items()
        })

        return graph

    def save(self, filepath: Path):
        """Save graph to file"""
        with open(filepath, 'wb') as f:
            pickle.dump(self.to_dict(), f)

    @classmethod
    def load(cls, filepath: Path) -> 'StakeholderGraph':
        """Load graph from file"""
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        return cls.from_dict(data)


def build_stakeholder_graph(chunks: List[Dict], doc_index: Dict) -> StakeholderGraph:
    """Build stakeholder graph from document chunks"""
    graph = StakeholderGraph()

    # Process each document
    processed_docs = set()
    for chunk in chunks:
        doc_id = chunk.get('doc_id', '')
        if doc_id in processed_docs:
            continue

        # Get full document content
        doc = doc_index.get(doc_id, {})
        content = doc.get('content', chunk.get('content', ''))
        metadata = chunk.get('metadata', {})

        if content:
            graph.process_document(doc_id, content, metadata)
            processed_docs.add(doc_id)

    return graph


if __name__ == "__main__":
    # Test the stakeholder graph
    test_content = """
    BEAT Healthcare Consulting at UCLA

    Project Team:
    - Danny Zhu, Project Lead
    - Rishit Jain, Financial Analyst
    - Rohit Guha, Market Research
    - Shawn Wang, Operations

    Client: Gil Travish, CEO of ViBo Health
    Contact: gtravish@vibohealth.com

    This healthcare market analysis was prepared by the BEAT consulting team.
    Rishit Jain conducted the financial modeling and valuation analysis.
    Danny Zhu led the client engagement and strategy development.

    The team specializes in healthcare strategy, market entry, and financial analysis.
    """

    graph = StakeholderGraph()
    graph.process_document("test_doc_001", test_content, {"file_name": "vibo_project.pdf"})

    print("=== Stakeholder Graph Stats ===")
    stats = graph.get_stats()
    print(f"People found: {stats['total_people']}")
    print(f"Projects: {stats['total_projects']}")
    print(f"Expertise domains: {stats['expertise_domains']}")
    print(f"Top mentioned: {stats['top_mentioned']}")

    print("\n=== Test Queries ===")

    # Who worked on project?
    result = graph.answer_who_question("Who worked on ViBo project?")
    print(f"\nQ: Who worked on ViBo project?")
    print(f"Found {len(result['results'])} people")

    # Who knows about finance?
    result = graph.answer_who_question("Who knows about financial analysis?")
    print(f"\nQ: Who knows about financial analysis?")
    for r in result['results']:
        print(f"  - {r['name']}: {r['expertise']}")

    # Who is Rishit?
    result = graph.answer_who_question("Who is Rishit Jain?")
    print(f"\nQ: Who is Rishit Jain?")
    if result['results']:
        r = result['results'][0]
        print(f"  Name: {r['name']}")
        print(f"  Roles: {r['roles']}")
        print(f"  Expertise: {r['expertise']}")
        print(f"  Projects: {r['projects']}")
