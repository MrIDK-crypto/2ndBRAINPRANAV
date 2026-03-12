# HIJ Partial Fixes — Design Document

Date: 2026-03-11

## Overview

Fix 4 partially-implemented features in the High Impact Journal predictor based on user feedback.

## Fix 1: Experiment Suggestions — Technical Correctness

**File:** `backend/services/experiment_suggestion_service.py`

Add `_validate_suggestions()` — a post-generation validation pass using a separate LLM call acting as a critical lab manager reviewer. Checks each suggestion against the paper's actual content for:
- Techniques not mentioned or supported by the paper
- Incompatible technique combinations
- Missing/wrong controls
- Unrealistic timelines
- Biological impossibilities

Adds `technical_issues` array to each suggestion. Uses temperature=0 for deterministic conservative validation. Filters out infeasible suggestions.

## Fix 2: Novelty Verification — Multi-Pass Search

**File:** `backend/services/novelty_verifier.py`

- Multi-pass search: if pass 1 returns 0 results, generate 2 alternative queries via LLM and retry
- Abstract comparison: include abstract text (already from OpenAlex) in verification prompt, not just titles
- Skeptical default: 0 results → confidence "low" + warning instead of "moderate"
- Score penalty: unchecked claims get 60 (uncertain) instead of 90 (likely_novel)

## Fix 3: Review Paper Analysis — Missing Assessments

**File:** `backend/services/paper_analysis_service.py`

- Expand `_analyze_review()` LLM prompt to extract predictiveness (predictive vs descriptive per conclusion) and practical_applicability (high/medium/low + reasoning)
- Add author reputation lookup via OpenAlex `/authors` API: search by name, get h-index and citation count for top 1-3 authors

## Fix 4: Journal Recommendations — Diversity & Quality Awareness

**File:** `backend/services/journal_scorer_service.py`

- Quality-aware sorting: use paper's overall score to adjust stretch/target/safe split
- Better per-journal reasoning explaining why it fits THIS paper
- Deduplicate journals across tiers
- Cap mega-journals to max 2 in safe tier

## Scope

~300 lines across 4 existing files. No new files, no schema changes, no new dependencies.
