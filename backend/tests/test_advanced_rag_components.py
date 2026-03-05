"""
Tests for Advanced RAG Components (Claude/Gemini-level features)

Tests the new components:
- QueryDecomposer - breaks complex queries into sub-queries
- SourceSynthesizer - pre-analyzes sources for conflicts/facts
- ContextCompressor - extracts query-relevant sentences
- AnswerEvaluator - self-correction loop

These tests work WITHOUT API keys (unit tests for logic).
"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.enhanced_search_service import (
    QueryDecomposer,
    SourceSynthesizer,
    ContextCompressor,
    AnswerEvaluator,
    QueryExpander,
    QueryClassifier,
    QueryContextualizer
)


# =============================================================================
# QUERY DECOMPOSER TESTS
# =============================================================================

class TestQueryDecomposer:
    """Test QueryDecomposer detection of complex queries"""

    def test_simple_query_not_decomposed(self):
        """Simple queries should not need decomposition"""
        decomposer = QueryDecomposer(client=None)

        simple_queries = [
            "What is RAG?",
            "How does search work?",
            "Tell me about documentation",
            "Where is the config file?",
        ]

        for q in simple_queries:
            assert not decomposer.needs_decomposition(q), f"'{q}' should NOT need decomposition"

    def test_compound_and_query_needs_decomposition(self):
        """Queries with 'and' should be decomposed"""
        decomposer = QueryDecomposer(client=None)

        compound_queries = [
            "What is RAG and how does it work?",
            "Explain authentication and authorization",
            "What are the features and limitations?",
        ]

        for q in compound_queries:
            assert decomposer.needs_decomposition(q), f"'{q}' SHOULD need decomposition"

    def test_comparison_query_needs_decomposition(self):
        """Comparison queries should be decomposed"""
        decomposer = QueryDecomposer(client=None)

        comparison_queries = [
            "RAG vs traditional search",
            "Compare MongoDB versus PostgreSQL",
            "What's the difference between REST and GraphQL?",
        ]

        for q in comparison_queries:
            assert decomposer.needs_decomposition(q), f"'{q}' SHOULD need decomposition"

    def test_multiple_questions_need_decomposition(self):
        """Multiple question marks indicate compound query"""
        decomposer = QueryDecomposer(client=None)

        assert decomposer.needs_decomposition("What is RAG? How does it improve search?")
        assert decomposer.needs_decomposition("Why use embeddings? What are the alternatives?")

    def test_long_query_needs_decomposition(self):
        """Very long queries (>15 words) likely need decomposition"""
        decomposer = QueryDecomposer(client=None)

        long_query = "Can you explain how the knowledge management system works with the document classification pipeline and what integrations are supported"
        assert decomposer.needs_decomposition(long_query)

    def test_decompose_without_client_returns_original(self):
        """Without LLM client, decompose returns original query"""
        decomposer = QueryDecomposer(client=None)

        result = decomposer.decompose("What is RAG and how does it compare to search?")
        assert result == ["What is RAG and how does it compare to search?"]


# =============================================================================
# CONTEXT COMPRESSOR TESTS
# =============================================================================

class TestContextCompressor:
    """Test ContextCompressor sentence extraction"""

    def test_extracts_relevant_sentences(self):
        """Should extract sentences containing query keywords"""
        query = "authentication flow"
        content = """
        The system uses OAuth2 for authentication. The authentication flow starts when a user clicks login.
        First, the user is redirected to the identity provider. Then tokens are exchanged.
        The weather is nice today. Birds are singing outside.
        After authentication, the user is granted access to their resources.
        """

        result = ContextCompressor.extract_relevant_sentences(query, content)

        # Should contain authentication-related sentences
        assert "authentication" in result.lower()
        assert "flow" in result.lower() or "OAuth2" in result

        # Should NOT contain irrelevant sentences
        assert "weather" not in result.lower()
        assert "birds" not in result.lower()

    def test_handles_empty_content(self):
        """Should handle empty content gracefully"""
        result = ContextCompressor.extract_relevant_sentences("test query", "")
        assert result == ""

    def test_handles_no_matching_sentences(self):
        """Should return empty when no sentences match"""
        query = "quantum computing algorithms"
        content = "The cat sat on the mat. The dog ran in the park."

        result = ContextCompressor.extract_relevant_sentences(query, content)
        # No overlap, should return empty or very short
        assert len(result) < 50

    def test_compress_sources_reduces_content(self):
        """compress_sources should reduce total content size"""
        query = "database configuration"
        sources = [
            {
                "title": "Setup Guide",
                "content": """
                This document explains database configuration in detail.
                The database uses PostgreSQL with specific configuration options.
                Configuration is stored in config.yaml file.

                Completely unrelated content about cooking recipes and travel tips
                that has nothing to do with databases or configuration at all.
                More filler text about random topics that shouldn't be included.
                """ * 10  # Repeat to make it long
            }
        ]

        compressed = ContextCompressor.compress_sources(query, sources)

        assert len(compressed) == 1
        assert compressed[0]['compressed_length'] < compressed[0]['original_length']
        # Relevant content should be kept
        assert "database" in compressed[0]['content'].lower() or "configuration" in compressed[0]['content'].lower()

    def test_preserves_multiple_relevant_sentences(self):
        """Should preserve multiple relevant sentences up to limit"""
        query = "API endpoints"
        content = """
        API endpoints are defined in routes.py.
        The API endpoints follow REST conventions.
        All API endpoints require authentication.
        Endpoints return JSON responses.
        Rate limiting applies to all API endpoints.
        """

        result = ContextCompressor.extract_relevant_sentences(query, content, max_sentences=3)

        # Should have multiple sentences
        assert result.count('.') >= 2


# =============================================================================
# ANSWER EVALUATOR TESTS
# =============================================================================

class TestAnswerEvaluator:
    """Test AnswerEvaluator quality checks (without LLM)"""

    def test_detects_short_answer(self):
        """Should flag very short answers for retry"""
        evaluator = AnswerEvaluator(client=None)

        result = evaluator.evaluate(
            query="Explain the authentication system",
            answer="Use OAuth.",
            sources=[]
        )

        assert result['quality_score'] < 0.5
        assert result['should_retry'] == True
        assert "short" in str(result['issues']).lower()

    def test_detects_no_info_with_sources(self):
        """Should flag when answer says no info but sources exist"""
        evaluator = AnswerEvaluator(client=None)

        result = evaluator.evaluate(
            query="How does authentication work?",
            answer="I don't have information about authentication in the provided sources.",
            sources=[{"content": "OAuth2 authentication is used for login."}]
        )

        assert result['quality_score'] < 0.7
        assert result['should_retry'] == True

    def test_accepts_good_answer(self):
        """Should accept reasonably long, informative answers"""
        evaluator = AnswerEvaluator(client=None)

        good_answer = """
        The authentication system uses OAuth2 protocol for secure login.
        When a user clicks login, they are redirected to the identity provider.
        After successful authentication, tokens are exchanged and stored securely.
        The access token is used for subsequent API calls, while the refresh token
        enables automatic token renewal without requiring the user to log in again.
        """

        result = evaluator.evaluate(
            query="How does authentication work?",
            answer=good_answer,
            sources=[{"content": "OAuth2 authentication..."}]
        )

        # Without LLM, should default to decent quality
        assert result['quality_score'] >= 0.5


# =============================================================================
# QUERY CLASSIFIER TESTS
# =============================================================================

class TestQueryClassifier:
    """Test query classification for adaptive retrieval"""

    def test_factual_classification(self):
        """Factual queries should be classified correctly"""
        factual_queries = [
            "What is RAG?",
            "Define retrieval augmented generation",
            "Who is the CEO?",
        ]

        for q in factual_queries:
            result = QueryClassifier.classify(q)
            assert result['type'] == 'FACTUAL', f"'{q}' should be FACTUAL"
            assert result['top_k'] == 5  # Fewer results for factual
            assert result['mmr_lambda'] == 0.8  # Higher relevance focus

    def test_procedural_classification(self):
        """How-to queries should be classified as PROCEDURAL"""
        procedural_queries = [
            "How do I set up authentication?",
            "How to configure the database?",
            "Steps to deploy the application",
        ]

        for q in procedural_queries:
            result = QueryClassifier.classify(q)
            assert result['type'] == 'PROCEDURAL', f"'{q}' should be PROCEDURAL"

    def test_exploratory_classification(self):
        """Broad queries should be classified as EXPLORATORY"""
        exploratory_queries = [
            "Tell me about the system architecture",
            "Explain the security model",
            "Overview of the platform",
        ]

        for q in exploratory_queries:
            result = QueryClassifier.classify(q)
            assert result['type'] == 'EXPLORATORY', f"'{q}' should be EXPLORATORY"
            assert result['top_k'] == 12  # More results for exploration

    def test_troubleshooting_classification(self):
        """Error/problem queries should be TROUBLESHOOTING"""
        troubleshooting_queries = [
            "Why doesn't login work?",
            "Authentication error fixing",
            "Problem with database connection",
        ]

        for q in troubleshooting_queries:
            result = QueryClassifier.classify(q)
            assert result['type'] == 'TROUBLESHOOTING', f"'{q}' should be TROUBLESHOOTING"

    def test_comparative_classification(self):
        """Comparison queries should be COMPARATIVE"""
        comparative_queries = [
            "RAG vs traditional search",
            "Compare OAuth and API keys",
            "Difference between SQL and NoSQL",
        ]

        for q in comparative_queries:
            result = QueryClassifier.classify(q)
            assert result['type'] == 'COMPARATIVE', f"'{q}' should be COMPARATIVE"
            assert result['mmr_lambda'] == 0.5  # High diversity for comparisons


# =============================================================================
# QUERY EXPANDER TESTS (Additional)
# =============================================================================

class TestQueryExpanderAdvanced:
    """Additional tests for query expander"""

    def test_complex_conversational_prefix(self):
        """Should strip complex conversational prefixes"""
        test_cases = [
            ("I want to know about the authentication system", "authentication system"),
            ("Could you explain the API design", "API design"),
            ("Please tell me about the database schema", "database schema"),
        ]

        for query, expected in test_cases:
            result = QueryExpander.extract_intent(query)
            assert expected.lower() in result.lower(), f"'{query}' -> expected '{expected}' in '{result}'"

    def test_keyword_extraction_filters_stopwords(self):
        """Keywords should not contain stopwords"""
        query = "Tell me about the authentication system and how it works"
        keywords = QueryExpander.get_keyword_terms(query)

        # Should NOT have common stopwords
        common_stopwords = {'tell', 'me', 'about', 'the', 'and', 'how'}
        for kw in keywords:
            assert kw not in common_stopwords, f"'{kw}' is a stopword, should not be in keywords"

        # Should have content words
        assert 'authentication' in keywords
        assert 'system' in keywords
        # "works" is kept as it's a content word in "how it works"


# =============================================================================
# INTEGRATION TEST
# =============================================================================

class TestAdvancedRAGIntegration:
    """Integration tests for the full pipeline (without API)"""

    def test_full_pipeline_structure(self):
        """Test that all components can be instantiated"""
        decomposer = QueryDecomposer(client=None)
        synthesizer = SourceSynthesizer(client=None)
        evaluator = AnswerEvaluator(client=None)
        contextualizer = QueryContextualizer(client=None)

        # All should be instantiated without error
        assert decomposer is not None
        assert synthesizer is not None
        assert evaluator is not None
        assert contextualizer is not None

    def test_contextualizer_detects_pronouns(self):
        """Contextualizer should detect queries needing context"""
        contextualizer = QueryContextualizer(client=None)

        needs_context = [
            "What about it?",
            "How does it work?",
            "Tell me more about this",
            "What are those for?",
        ]

        no_context = [
            "What is RAG?",
            "How does authentication work?",
            "Explain the system architecture",
        ]

        for q in needs_context:
            assert contextualizer.needs_contextualization(q), f"'{q}' SHOULD need context"

        for q in no_context:
            assert not contextualizer.needs_contextualization(q), f"'{q}' should NOT need context"

    def test_compression_integration(self):
        """Test compression works in realistic scenario"""
        query = "How do I configure the database connection?"
        sources = [
            {
                "title": "Database Setup",
                "content": """
                To configure the database connection, you need to set environment variables.
                The DATABASE_URL environment variable should contain the connection string.
                Make sure PostgreSQL is installed and running before configuration.

                Random unrelated content about JavaScript frameworks.
                More content about frontend development.
                CSS styling tips and tricks.
                """
            },
            {
                "title": "Connection Guide",
                "content": """
                Database connection requires proper credentials.
                Configure connection pooling for production environments.
                The connection timeout should be set to 30 seconds.

                Unrelated content about cooking and recipes.
                Travel destinations and vacation planning.
                """
            }
        ]

        compressed = ContextCompressor.compress_sources(query, sources)

        # Should have compressed both
        assert len(compressed) == 2

        # Total content should be smaller
        original_total = sum(len(s['content']) for s in sources)
        compressed_total = sum(s['compressed_length'] for s in compressed)
        assert compressed_total < original_total


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
