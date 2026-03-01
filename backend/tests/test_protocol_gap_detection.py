"""
Tests for Protocol Gap Detection Enhancement
=============================================
Tests the protocol training pipeline and its integration with IntelligentGapDetector.
"""

import os
import sys
import json
import pytest

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# =============================================================================
# Unit Tests: Protocol Pattern Detection
# =============================================================================

class TestProtocolPatterns:
    """Test protocol_patterns.py content detection."""

    def test_is_protocol_content_positive(self):
        """Protocol text should be detected as protocol content."""
        from services.protocol_patterns import is_protocol_content

        protocol_text = (
            "1. Pipette 10 µL of sample into a 1.5 mL microcentrifuge tube. "
            "2. Add 90 µL of PBS buffer (pH 7.4). "
            "3. Vortex for 10 seconds. "
            "4. Centrifuge at 12,000 rpm for 5 minutes at 4°C. "
            "5. Carefully aspirate the supernatant. "
            "6. Resuspend the pellet in 50 µL of lysis buffer."
        )
        is_protocol, confidence = is_protocol_content(protocol_text)
        assert is_protocol is True
        assert confidence > 0.3

    def test_is_protocol_content_negative(self):
        """Business text should NOT be detected as protocol content."""
        from services.protocol_patterns import is_protocol_content

        business_text = (
            "We decided to migrate the CRM to Salesforce because of better scalability. "
            "The team agreed this was the best approach. John will lead the implementation "
            "starting January 15. Budget approved at $100K. Q2 OKR review showed revenue "
            "target was exceeded. Customer satisfaction score: 8.2/10."
        )
        is_protocol, confidence = is_protocol_content(business_text)
        assert is_protocol is False
        assert confidence < 0.5

    def test_is_protocol_content_short_text(self):
        """Short text should return False."""
        from services.protocol_patterns import is_protocol_content

        is_protocol, confidence = is_protocol_content("short")
        assert is_protocol is False
        assert confidence == 0.0

    def test_is_protocol_content_empty(self):
        """Empty text should return False."""
        from services.protocol_patterns import is_protocol_content

        is_protocol, confidence = is_protocol_content("")
        assert is_protocol is False


# =============================================================================
# Unit Tests: Frame Templates
# =============================================================================

class TestProtocolFrameTemplates:
    """Test that protocol frame templates are properly structured."""

    def test_protocol_frames_loaded(self):
        """Protocol frame templates should be loadable."""
        from services.protocol_patterns import PROTOCOL_FRAME_TEMPLATES

        assert "PROTOCOL_STEP" in PROTOCOL_FRAME_TEMPLATES
        assert "REAGENT_USAGE" in PROTOCOL_FRAME_TEMPLATES
        assert "EQUIPMENT_SETUP" in PROTOCOL_FRAME_TEMPLATES
        assert "SAFETY_PRECAUTION" in PROTOCOL_FRAME_TEMPLATES
        assert "EXPECTED_RESULT" in PROTOCOL_FRAME_TEMPLATES

    def test_frame_structure(self):
        """Each frame should have required, optional, and triggers."""
        from services.protocol_patterns import PROTOCOL_FRAME_TEMPLATES

        for name, frame in PROTOCOL_FRAME_TEMPLATES.items():
            assert "required" in frame, f"{name} missing 'required'"
            assert "optional" in frame, f"{name} missing 'optional'"
            assert "triggers" in frame, f"{name} missing 'triggers'"
            assert len(frame["triggers"]) > 0, f"{name} has no triggers"

    def test_protocol_step_triggers(self):
        """PROTOCOL_STEP should match common lab actions."""
        import re
        from services.protocol_patterns import PROTOCOL_FRAME_TEMPLATES

        triggers = PROTOCOL_FRAME_TEMPLATES["PROTOCOL_STEP"]["triggers"]
        test_sentences = [
            "Pipette 10 µL of sample into a tube",
            "Incubate at 37°C for 1 hour",
            "Centrifuge at 12000 rpm for 5 minutes",
            "Wash with PBS 3 times",
        ]

        for sentence in test_sentences:
            matched = any(re.search(t, sentence, re.IGNORECASE) for t in triggers)
            assert matched, f"No trigger matched: '{sentence}'"


# =============================================================================
# Unit Tests: Missing Patterns
# =============================================================================

class TestProtocolMissingPatterns:
    """Test protocol-specific missing patterns."""

    def test_missing_patterns_loaded(self):
        """Protocol missing patterns should be loadable."""
        from services.protocol_patterns import PROTOCOL_MISSING_PATTERNS

        assert "VAGUE_PARAMETER" in PROTOCOL_MISSING_PATTERNS
        assert "MISSING_CONCENTRATION" in PROTOCOL_MISSING_PATTERNS
        assert "MISSING_DURATION" in PROTOCOL_MISSING_PATTERNS
        assert "MISSING_TEMPERATURE" in PROTOCOL_MISSING_PATTERNS
        assert "MISSING_SAFETY_INFO" in PROTOCOL_MISSING_PATTERNS

    def test_vague_parameter_detection(self):
        """Vague parameters should be detected."""
        import re
        from services.protocol_patterns import PROTOCOL_MISSING_PATTERNS

        vague_patterns = PROTOCOL_MISSING_PATTERNS["VAGUE_PARAMETER"]
        vague_texts = [
            "Vortex briefly",
            "Mix gently",
            "Incubate overnight",
            "Keep at room temperature",
        ]

        for text in vague_texts:
            matched = any(re.search(p, text, re.IGNORECASE) for p in vague_patterns)
            assert matched, f"Vague pattern not detected: '{text}'"


# =============================================================================
# Integration Test: IntelligentGapDetector with Protocol Content
# =============================================================================

class TestProtocolIntegration:
    """Test protocol patterns integrated into IntelligentGapDetector."""

    def test_frame_templates_merged(self):
        """Protocol frame templates should be merged into main FRAME_TEMPLATES."""
        from services.intelligent_gap_detector import FRAME_TEMPLATES

        # Original frames should still be there
        assert "DECISION" in FRAME_TEMPLATES
        assert "PROCESS" in FRAME_TEMPLATES

        # Protocol frames should be merged
        assert "PROTOCOL_STEP" in FRAME_TEMPLATES
        assert "REAGENT_USAGE" in FRAME_TEMPLATES
        assert "SAFETY_PRECAUTION" in FRAME_TEMPLATES

    def test_missing_patterns_merged(self):
        """Protocol missing patterns should be merged into main MISSING_PATTERNS."""
        from services.intelligent_gap_detector import MISSING_PATTERNS

        # Original patterns should still be there
        assert "MISSING_RATIONALE" in MISSING_PATTERNS
        assert "MISSING_AGENT" in MISSING_PATTERNS

        # Protocol patterns should be merged
        assert "VAGUE_PARAMETER" in MISSING_PATTERNS
        assert "MISSING_CONCENTRATION" in MISSING_PATTERNS

    def test_detector_processes_protocol(self):
        """Detector should process protocol content and generate gaps."""
        from services.intelligent_gap_detector import IntelligentGapDetector

        detector = IntelligentGapDetector()

        protocol_doc = (
            "RNA Extraction Protocol\n"
            "1. Add TRIzol to cells and incubate briefly.\n"
            "2. Add chloroform and shake vigorously.\n"
            "3. Centrifuge to separate phases.\n"
            "4. Transfer aqueous phase to new tube.\n"
            "5. Add isopropanol and incubate overnight.\n"
            "6. Wash pellet with ethanol.\n"
            "7. Resuspend in water.\n"
        )

        detector.add_document("doc1", "RNA Extraction", protocol_doc)
        result = detector.analyze()

        assert "gaps" in result
        assert "stats" in result
        assert result["stats"]["total_frames"] > 0

    def test_detector_no_regression_business(self):
        """Business documents should still generate standard gaps (no protocol gaps)."""
        from services.intelligent_gap_detector import IntelligentGapDetector

        detector = IntelligentGapDetector()

        business_doc = (
            "We decided to switch to AWS because it was cheaper. "
            "The migration will happen eventually. Someone mentioned "
            "we should also update the documentation. As you know, "
            "the usual process for deployments has changed."
        )

        detector.add_document("doc2", "Migration Notes", business_doc)
        result = detector.analyze()

        assert "gaps" in result
        # Should still find business-type gaps
        gap_types = [g.gap_type for g in result["gaps"]]
        assert any("MISSING" in gt for gt in gap_types)

    def test_category_mapping(self):
        """Protocol frame types should map to correct categories."""
        from services.intelligent_gap_detector import GroundedQuestionGenerator

        gen = GroundedQuestionGenerator()
        assert gen._frame_to_category("PROTOCOL_STEP") == "process"
        assert gen._frame_to_category("REAGENT_USAGE") == "technical"
        assert gen._frame_to_category("SAFETY_PRECAUTION") == "safety"
        assert gen._frame_to_category("EXPECTED_RESULT") == "outcome"
        # Original mappings unchanged
        assert gen._frame_to_category("DECISION") == "decision"
        assert gen._frame_to_category("PROCESS") == "process"


# =============================================================================
# Unit Tests: Pattern Miner
# =============================================================================

class TestPatternMiner:
    """Test the pattern mining module."""

    def test_mine_action_verbs(self):
        """Should mine action verbs from protocols."""
        from protocol_training.pattern_miner import mine_action_verbs

        protocols = [
            {
                "steps": [
                    {"action_verb": "pipette", "text": "Pipette 10 µL"},
                    {"action_verb": "centrifuge", "text": "Centrifuge at 12000 rpm"},
                    {"action_verb": "incubate", "text": "Incubate at 37°C"},
                ]
            }
        ]

        result = mine_action_verbs(protocols)
        assert "all_verbs" in result
        assert "pipette" in result["all_verbs"]
        assert "centrifuge" in result["all_verbs"]
        assert "incubate" in result["all_verbs"]

    def test_generate_runtime_module(self):
        """Should generate valid Python module code."""
        from protocol_training.pattern_miner import generate_runtime_module, SEED_ACTION_VERBS

        patterns = {"action_verbs": {"all_verbs": sorted(SEED_ACTION_VERBS)}}
        code = generate_runtime_module(patterns)

        # Should be valid Python
        import ast
        ast.parse(code)

        # Should contain key exports
        assert "PROTOCOL_FRAME_TEMPLATES" in code
        assert "PROTOCOL_MISSING_PATTERNS" in code
        assert "PROTOCOL_QUESTION_TEMPLATES" in code
        assert "is_protocol_content" in code


# =============================================================================
# Unit Tests: Normalizer
# =============================================================================

class TestNormalizer:
    """Test the corpus normalizer."""

    def test_deduplicate(self):
        """Should deduplicate protocols by title."""
        from protocol_training.normalizer import _deduplicate

        protocols = [
            {"title": "PCR Protocol", "steps": [{"order": 1}]},
            {"title": "pcr protocol", "steps": [{"order": 1}, {"order": 2}]},
            {"title": "Western Blot", "steps": [{"order": 1}]},
        ]

        unique = _deduplicate(protocols)
        assert len(unique) == 2

        # Should keep the one with more steps
        pcr = [p for p in unique if "pcr" in p["title"].lower()][0]
        assert len(pcr["steps"]) == 2

    def test_compute_stats(self):
        """Should compute corpus statistics."""
        from protocol_training.normalizer import _compute_stats

        protocols = [
            {
                "source": "chemh",
                "domain": "chemistry",
                "steps": [
                    {"action_verb": "add", "text": "Add reagent"},
                    {"action_verb": "mix", "text": "Mix well"},
                ],
                "reagents": ["ethanol", "water"],
                "equipment": ["pipette"],
                "safety_notes": ["Use fume hood"],
            },
            {
                "source": "wlp",
                "domain": "biology",
                "steps": [{"action_verb": "incubate", "text": "Incubate"}],
                "reagents": ["PBS"],
                "equipment": [],
                "safety_notes": [],
            },
        ]

        stats = _compute_stats(protocols)
        assert stats["total_protocols"] == 2
        assert stats["total_steps"] == 3
        assert stats["avg_steps_per_protocol"] == 1.5
        assert stats["by_source"]["chemh"] == 1
        assert stats["by_source"]["wlp"] == 1
        assert stats["protocols_with_reagents"] == 2
        assert stats["protocols_with_equipment"] == 1
        assert stats["protocols_with_safety"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
