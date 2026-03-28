"""Tests for the Intent Gate (Layer 1)."""

import pytest
from services.chat_orchestrator.intent_gate import IntentGate


@pytest.fixture
def gate():
    return IntentGate()


class TestKeywordDetection:
    def test_hij_keywords(self, gate):
        result = gate.classify("Can you score my manuscript for Nature?")
        assert "hij" in result["powers"]

    def test_competitor_keywords(self, gate):
        result = gate.classify("Find competitors in CRISPR delivery")
        assert "competitor_finder" in result["powers"]

    def test_idea_keywords(self, gate):
        result = gate.classify("Is this idea novel? Validate my research concept")
        assert "idea_reality" in result["powers"]

    def test_co_researcher_keywords(self, gate):
        result = gate.classify("Help me brainstorm research hypotheses")
        assert "co_researcher" in result["powers"]

    def test_no_power_detected(self, gate):
        result = gate.classify("What was discussed in yesterday's meeting?")
        assert result["powers"] == []
        assert result["needs_powers"] is False

    def test_multi_intent(self, gate):
        result = gate.classify("Score my paper and find competitors")
        assert "hij" in result["powers"]
        assert "competitor_finder" in result["powers"]

    def test_explicit_trigger_bypass(self, gate):
        result = gate.classify("analyze this", power_hint="hij")
        assert result["powers"] == ["hij"]
        assert result["needs_powers"] is True
        assert result["skip_router"] is True


class TestClassifyOutput:
    def test_output_shape(self, gate):
        result = gate.classify("Score my manuscript")
        assert "needs_powers" in result
        assert "powers" in result
        assert "skip_router" in result
        assert isinstance(result["powers"], list)
        assert isinstance(result["needs_powers"], bool)
