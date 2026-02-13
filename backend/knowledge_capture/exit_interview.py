"""
Exit Interview Module
Structured questions to capture tacit knowledge from departing employees.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any
from enum import Enum
import json
from pathlib import Path


class QuestionCategory(Enum):
    """Categories of exit interview questions"""
    ROLE_SPECIFIC = "role_specific"
    RELATIONSHIPS = "relationships"
    PROCESSES = "processes"
    LESSONS_LEARNED = "lessons_learned"
    INSTITUTIONAL_KNOWLEDGE = "institutional_knowledge"
    HANDOFF = "handoff"
    ADVICE = "advice"


@dataclass
class Question:
    """A single exit interview question"""
    id: str
    text: str
    category: QuestionCategory
    follow_ups: List[str] = field(default_factory=list)
    required: bool = True
    help_text: str = ""
    expected_type: str = "text"  # text, list, rating, choice


@dataclass
class Answer:
    """An answer to an exit interview question"""
    question_id: str
    answer_text: str
    timestamp: datetime = field(default_factory=datetime.now)
    follow_up_answers: Dict[str, str] = field(default_factory=dict)


@dataclass
class ExitInterviewSession:
    """A complete exit interview session"""
    session_id: str
    employee_name: str
    employee_role: str
    department: str
    start_time: datetime
    end_time: Optional[datetime] = None
    answers: List[Answer] = field(default_factory=list)
    status: str = "in_progress"  # in_progress, completed, cancelled
    metadata: Dict[str, Any] = field(default_factory=dict)


class ExitInterviewManager:
    """
    Manages exit interview sessions and question templates.
    Captures tacit knowledge that isn't in documents.
    """

    # Core question bank organized by category
    QUESTION_BANK: Dict[QuestionCategory, List[Question]] = {
        QuestionCategory.ROLE_SPECIFIC: [
            Question(
                id="role_1",
                text="What are the 3-5 most critical tasks in your role that must continue after you leave?",
                category=QuestionCategory.ROLE_SPECIFIC,
                follow_ups=[
                    "Which of these tasks has the steepest learning curve?",
                    "What resources or documentation exists for each task?"
                ],
                help_text="Focus on tasks that are essential for day-to-day operations"
            ),
            Question(
                id="role_2",
                text="What recurring deadlines or cyclical responsibilities does your role have?",
                category=QuestionCategory.ROLE_SPECIFIC,
                follow_ups=[
                    "Are there any upcoming deadlines in the next 3-6 months?",
                    "What preparation is typically needed for each deadline?"
                ]
            ),
            Question(
                id="role_3",
                text="What tools, systems, or software do you use daily? Any tips or shortcuts?",
                category=QuestionCategory.ROLE_SPECIFIC,
                follow_ups=[
                    "Are there any workarounds you've developed for system limitations?",
                    "Which tools took the longest to master?"
                ]
            ),
            Question(
                id="role_4",
                text="What aspects of your work are NOT documented but should be?",
                category=QuestionCategory.ROLE_SPECIFIC,
                help_text="This captures tacit knowledge gaps"
            ),
            Question(
                id="role_5",
                text="What decisions do you regularly make? What criteria do you use?",
                category=QuestionCategory.ROLE_SPECIFIC,
                follow_ups=[
                    "Can you walk through a recent example of such a decision?"
                ]
            )
        ],

        QuestionCategory.RELATIONSHIPS: [
            Question(
                id="rel_1",
                text="Who are your key internal contacts for different issues? (Create a contact map)",
                category=QuestionCategory.RELATIONSHIPS,
                follow_ups=[
                    "For each contact, what's the best way to communicate with them?",
                    "Are there any relationship dynamics the new person should know about?"
                ],
                expected_type="list"
            ),
            Question(
                id="rel_2",
                text="Who are the key external stakeholders (clients, vendors, partners)?",
                category=QuestionCategory.RELATIONSHIPS,
                follow_ups=[
                    "What's the history of each relationship?",
                    "Any ongoing issues or opportunities with these stakeholders?"
                ]
            ),
            Question(
                id="rel_3",
                text="Who do you go to when you need quick answers or advice?",
                category=QuestionCategory.RELATIONSHIPS,
                help_text="Identifies informal knowledge networks"
            ),
            Question(
                id="rel_4",
                text="Are there any relationships that need special attention or repair?",
                category=QuestionCategory.RELATIONSHIPS,
                required=False
            ),
            Question(
                id="rel_5",
                text="Who has been most helpful to you in your role? What did they help with?",
                category=QuestionCategory.RELATIONSHIPS
            )
        ],

        QuestionCategory.PROCESSES: [
            Question(
                id="proc_1",
                text="What workarounds or unofficial processes have you developed?",
                category=QuestionCategory.PROCESSES,
                help_text="These are often the most valuable pieces of tacit knowledge"
            ),
            Question(
                id="proc_2",
                text="Which official processes don't work well in practice? What do you do instead?",
                category=QuestionCategory.PROCESSES,
                follow_ups=[
                    "Why do you think the official process doesn't work?",
                    "Have you suggested improvements? What was the response?"
                ]
            ),
            Question(
                id="proc_3",
                text="What approvals or sign-offs are needed for common tasks? Any shortcuts?",
                category=QuestionCategory.PROCESSES
            ),
            Question(
                id="proc_4",
                text="What's the typical timeline for key processes? Any bottlenecks?",
                category=QuestionCategory.PROCESSES
            ),
            Question(
                id="proc_5",
                text="Are there any recurring meetings that are important? What's their purpose and dynamics?",
                category=QuestionCategory.PROCESSES
            )
        ],

        QuestionCategory.LESSONS_LEARNED: [
            Question(
                id="lessons_1",
                text="What mistakes did you make early on that you'd want your successor to avoid?",
                category=QuestionCategory.LESSONS_LEARNED,
                follow_ups=[
                    "What would you do differently knowing what you know now?"
                ]
            ),
            Question(
                id="lessons_2",
                text="What do you wish someone had told you when you started?",
                category=QuestionCategory.LESSONS_LEARNED
            ),
            Question(
                id="lessons_3",
                text="What's the biggest challenge in this role? How did you handle it?",
                category=QuestionCategory.LESSONS_LEARNED,
                follow_ups=[
                    "Are there any ongoing challenges that haven't been solved?"
                ]
            ),
            Question(
                id="lessons_4",
                text="What failed projects or initiatives should the team learn from?",
                category=QuestionCategory.LESSONS_LEARNED,
                follow_ups=[
                    "What were the warning signs?",
                    "What would you do differently?"
                ]
            ),
            Question(
                id="lessons_5",
                text="What successful projects are you most proud of? What made them work?",
                category=QuestionCategory.LESSONS_LEARNED
            )
        ],

        QuestionCategory.INSTITUTIONAL_KNOWLEDGE: [
            Question(
                id="inst_1",
                text="Why were certain decisions made? What was the context?",
                category=QuestionCategory.INSTITUTIONAL_KNOWLEDGE,
                help_text="Capture the 'why' behind current practices"
            ),
            Question(
                id="inst_2",
                text="What historical context is important for understanding current projects or relationships?",
                category=QuestionCategory.INSTITUTIONAL_KNOWLEDGE
            ),
            Question(
                id="inst_3",
                text="Are there any 'unwritten rules' in the team or organization?",
                category=QuestionCategory.INSTITUTIONAL_KNOWLEDGE
            ),
            Question(
                id="inst_4",
                text="What are the organization's sacred cows or sensitive topics?",
                category=QuestionCategory.INSTITUTIONAL_KNOWLEDGE,
                required=False
            ),
            Question(
                id="inst_5",
                text="What traditions, rituals, or practices are important to the team culture?",
                category=QuestionCategory.INSTITUTIONAL_KNOWLEDGE
            )
        ],

        QuestionCategory.HANDOFF: [
            Question(
                id="handoff_1",
                text="What's currently in progress? What's the status of each item?",
                category=QuestionCategory.HANDOFF,
                expected_type="list"
            ),
            Question(
                id="handoff_2",
                text="What's coming up in the next 30/60/90 days?",
                category=QuestionCategory.HANDOFF
            ),
            Question(
                id="handoff_3",
                text="Where are all the important files, documents, and resources located?",
                category=QuestionCategory.HANDOFF,
                follow_ups=[
                    "Are there any password-protected resources?",
                    "Who has access to what?"
                ]
            ),
            Question(
                id="handoff_4",
                text="What email threads or communication channels should your successor monitor?",
                category=QuestionCategory.HANDOFF
            ),
            Question(
                id="handoff_5",
                text="Are there any time-sensitive items that need immediate attention?",
                category=QuestionCategory.HANDOFF
            )
        ],

        QuestionCategory.ADVICE: [
            Question(
                id="advice_1",
                text="What advice would you give to someone starting in your role tomorrow?",
                category=QuestionCategory.ADVICE
            ),
            Question(
                id="advice_2",
                text="What should your successor prioritize in their first week/month?",
                category=QuestionCategory.ADVICE
            ),
            Question(
                id="advice_3",
                text="What quick wins can build credibility early?",
                category=QuestionCategory.ADVICE
            ),
            Question(
                id="advice_4",
                text="What should your successor absolutely NOT do?",
                category=QuestionCategory.ADVICE
            ),
            Question(
                id="advice_5",
                text="Is there anything else you think we should capture before you leave?",
                category=QuestionCategory.ADVICE,
                help_text="Open-ended to catch anything we missed"
            )
        ]
    }

    def __init__(self, storage_dir: Path = None):
        self.storage_dir = storage_dir or Path("./exit_interviews")
        self.storage_dir.mkdir(exist_ok=True)
        self.sessions: Dict[str, ExitInterviewSession] = {}

    def get_all_questions(self) -> List[Question]:
        """Get all questions from all categories"""
        questions = []
        for category_questions in self.QUESTION_BANK.values():
            questions.extend(category_questions)
        return questions

    def get_questions_by_category(self, category: QuestionCategory) -> List[Question]:
        """Get questions for a specific category"""
        return self.QUESTION_BANK.get(category, [])

    def get_required_questions(self) -> List[Question]:
        """Get only required questions"""
        return [q for q in self.get_all_questions() if q.required]

    def create_session(
        self,
        employee_name: str,
        employee_role: str,
        department: str,
        metadata: Dict = None
    ) -> ExitInterviewSession:
        """Create a new exit interview session"""
        session_id = f"exit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{employee_name.replace(' ', '_')}"

        session = ExitInterviewSession(
            session_id=session_id,
            employee_name=employee_name,
            employee_role=employee_role,
            department=department,
            start_time=datetime.now(),
            metadata=metadata or {}
        )

        self.sessions[session_id] = session
        self._save_session(session)

        return session

    def record_answer(
        self,
        session_id: str,
        question_id: str,
        answer_text: str,
        follow_up_answers: Dict[str, str] = None
    ) -> bool:
        """Record an answer to a question"""
        if session_id not in self.sessions:
            return False

        session = self.sessions[session_id]

        answer = Answer(
            question_id=question_id,
            answer_text=answer_text,
            follow_up_answers=follow_up_answers or {}
        )

        session.answers.append(answer)
        self._save_session(session)

        return True

    def complete_session(self, session_id: str) -> Optional[ExitInterviewSession]:
        """Mark a session as complete"""
        if session_id not in self.sessions:
            return None

        session = self.sessions[session_id]
        session.end_time = datetime.now()
        session.status = "completed"

        self._save_session(session)

        return session

    def get_session(self, session_id: str) -> Optional[ExitInterviewSession]:
        """Get a session by ID"""
        return self.sessions.get(session_id)

    def get_session_progress(self, session_id: str) -> Dict:
        """Get progress statistics for a session"""
        if session_id not in self.sessions:
            return {"error": "Session not found"}

        session = self.sessions[session_id]
        all_questions = self.get_all_questions()
        required_questions = self.get_required_questions()

        answered_ids = {a.question_id for a in session.answers}

        return {
            "session_id": session_id,
            "employee_name": session.employee_name,
            "status": session.status,
            "total_questions": len(all_questions),
            "required_questions": len(required_questions),
            "answered": len(session.answers),
            "required_answered": len([q for q in required_questions if q.id in answered_ids]),
            "completion_percentage": (len(session.answers) / len(all_questions)) * 100,
            "remaining": [q.id for q in all_questions if q.id not in answered_ids]
        }

    def export_session_to_document(self, session_id: str) -> str:
        """Export session as a document for RAG indexing"""
        if session_id not in self.sessions:
            return ""

        session = self.sessions[session_id]

        # Build document
        doc_parts = [
            f"# Exit Interview: {session.employee_name}",
            f"**Role:** {session.employee_role}",
            f"**Department:** {session.department}",
            f"**Date:** {session.start_time.strftime('%Y-%m-%d')}",
            "",
            "---",
            ""
        ]

        # Group answers by category
        question_map = {q.id: q for q in self.get_all_questions()}

        for category in QuestionCategory:
            category_answers = []
            for answer in session.answers:
                question = question_map.get(answer.question_id)
                if question and question.category == category:
                    category_answers.append((question, answer))

            if category_answers:
                doc_parts.append(f"## {category.value.replace('_', ' ').title()}")
                doc_parts.append("")

                for question, answer in category_answers:
                    doc_parts.append(f"**Q: {question.text}**")
                    doc_parts.append(f"A: {answer.answer_text}")

                    if answer.follow_up_answers:
                        for fu_q, fu_a in answer.follow_up_answers.items():
                            doc_parts.append(f"  - {fu_q}")
                            doc_parts.append(f"    {fu_a}")

                    doc_parts.append("")

        return "\n".join(doc_parts)

    def _save_session(self, session: ExitInterviewSession):
        """Save session to file"""
        session_file = self.storage_dir / f"{session.session_id}.json"

        data = {
            "session_id": session.session_id,
            "employee_name": session.employee_name,
            "employee_role": session.employee_role,
            "department": session.department,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "status": session.status,
            "metadata": session.metadata,
            "answers": [
                {
                    "question_id": a.question_id,
                    "answer_text": a.answer_text,
                    "timestamp": a.timestamp.isoformat(),
                    "follow_up_answers": a.follow_up_answers
                }
                for a in session.answers
            ]
        }

        with open(session_file, 'w') as f:
            json.dump(data, f, indent=2)

    def load_session(self, session_id: str) -> Optional[ExitInterviewSession]:
        """Load session from file"""
        session_file = self.storage_dir / f"{session_id}.json"

        if not session_file.exists():
            return None

        with open(session_file, 'r') as f:
            data = json.load(f)

        session = ExitInterviewSession(
            session_id=data["session_id"],
            employee_name=data["employee_name"],
            employee_role=data["employee_role"],
            department=data["department"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            status=data["status"],
            metadata=data.get("metadata", {}),
            answers=[
                Answer(
                    question_id=a["question_id"],
                    answer_text=a["answer_text"],
                    timestamp=datetime.fromisoformat(a["timestamp"]),
                    follow_up_answers=a.get("follow_up_answers", {})
                )
                for a in data.get("answers", [])
            ]
        )

        self.sessions[session_id] = session
        return session


# Global instance
exit_interview_manager = ExitInterviewManager()


if __name__ == "__main__":
    # Demo the exit interview system
    manager = ExitInterviewManager()

    # Create a session
    session = manager.create_session(
        employee_name="Rishit Jain",
        employee_role="Healthcare Consultant",
        department="BEAT Healthcare Consulting"
    )

    print(f"Created session: {session.session_id}")

    # Get questions
    print(f"\nTotal questions: {len(manager.get_all_questions())}")
    print(f"Required questions: {len(manager.get_required_questions())}")

    # Show questions by category
    for category in QuestionCategory:
        questions = manager.get_questions_by_category(category)
        print(f"\n{category.value}: {len(questions)} questions")
        for q in questions[:2]:
            print(f"  - {q.text[:60]}...")

    # Record some sample answers
    manager.record_answer(
        session.session_id,
        "role_1",
        "1. Client presentations 2. Financial modeling 3. Project documentation 4. Team coordination",
        {"Which of these tasks has the steepest learning curve?": "Financial modeling takes about 2-3 months to get comfortable with"}
    )

    manager.record_answer(
        session.session_id,
        "rel_1",
        "For UCLA Health projects: Contact Dr. Smith in Pediatrics. For financial questions: Talk to Finance team lead Sarah. For IT issues: John in the tech team.",
    )

    # Get progress
    progress = manager.get_session_progress(session.session_id)
    print(f"\nProgress: {progress['answered']}/{progress['total_questions']} ({progress['completion_percentage']:.1f}%)")

    # Export to document
    doc = manager.export_session_to_document(session.session_id)
    print(f"\n--- Exported Document Preview ---")
    print(doc[:500] + "...")
