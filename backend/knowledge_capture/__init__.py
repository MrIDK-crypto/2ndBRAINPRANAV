"""
Knowledge Capture Module
Tools for capturing tacit knowledge from employees.
"""

from .exit_interview import (
    ExitInterviewManager,
    ExitInterviewSession,
    Question,
    Answer,
    QuestionCategory,
    exit_interview_manager
)

__all__ = [
    'ExitInterviewManager',
    'ExitInterviewSession',
    'Question',
    'Answer',
    'QuestionCategory',
    'exit_interview_manager'
]
