"""
Protocol ML Classifier Training
=================================
Trains 3 scikit-learn classifiers using protocol corpus data:

1. Content Type Classifier: protocol vs business text (>90% accuracy target)
2. Missing Step Detector: predict if a step is missing between two consecutive steps
3. Protocol Completeness Scorer: score protocol completeness (0-1)

All models use TF-IDF + lightweight classifiers for zero-GPT-cost inference.
Serialized to joblib for fast loading at runtime.

Usage:
    python -m protocol_training.train_classifier
"""

import os
import json
import logging
import re
import random
from typing import List, Dict, Any, Tuple, Optional

from . import CORPUS_DIR, MODELS_DIR

logger = logging.getLogger(__name__)

# Output paths
CONTENT_CLASSIFIER_PATH = os.path.join(MODELS_DIR, 'content_classifier.joblib')
MISSING_STEP_PATH = os.path.join(MODELS_DIR, 'missing_step_detector.joblib')
COMPLETENESS_PATH = os.path.join(MODELS_DIR, 'completeness_scorer.joblib')


def _load_protocol_texts() -> List[str]:
    """Load protocol texts from unified corpus."""
    filepath = os.path.join(CORPUS_DIR, 'unified_corpus.jsonl')
    texts = []
    if not os.path.exists(filepath):
        logger.warning('[Trainer] Unified corpus not found')
        return texts

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    p = json.loads(line)
                    text = p.get('raw_text', '')
                    if text and len(text) > 100:
                        texts.append(text[:5000])
                except json.JSONDecodeError:
                    continue
    return texts


def _generate_business_texts() -> List[str]:
    """Generate synthetic business document texts for negative class."""
    templates = [
        "We decided to migrate the {system} to {platform} because {reason}. The team agreed this was the best approach. "
        "John will lead the implementation starting {date}. Budget approved at ${amount}K.",

        "Meeting notes from {date}: Discussed {topic} with the team. Key decisions: "
        "1) {decision1} 2) {decision2}. Action items assigned to {person}. Follow-up scheduled for next week.",

        "Q{quarter} OKR Review: Revenue target of ${amount}M was {status}. Customer satisfaction score: {score}/10. "
        "Team velocity improved by {percent}%. Key risks: {risk}. Mitigation plan in progress.",

        "Incident report: {system} experienced downtime on {date}. Root cause: {cause}. "
        "Impact: {impact}. Resolution: {resolution}. Post-mortem scheduled for {date2}.",

        "Project status update: {project} is {percent}% complete. Milestones achieved: {milestone}. "
        "Blockers: {blocker}. ETA for completion: {date}. Stakeholder review pending.",

        "New hire onboarding checklist for {role}: 1) Set up {system} access 2) Complete {training} "
        "3) Meet with {person} 4) Review {document}. Manager: {manager}.",

        "Budget allocation for {quarter}: Engineering ${amount}K, Marketing ${amount2}K, Operations ${amount3}K. "
        "Headcount plan: {count} new hires. Capital expenditure: ${capex}K for {item}.",

        "Customer feedback summary: {count} tickets this month. Top issues: {issue1}, {issue2}. "
        "NPS score: {score}. Churn rate: {percent}%. Retention strategy: {strategy}.",

        "Product roadmap update: Feature {feature} launching in {month}. Beta testing with {count} users. "
        "A/B test results: variant B improved conversion by {percent}%. Rolling out to all users.",

        "Vendor evaluation: Comparing {vendor1} vs {vendor2} for {service}. Pricing: ${price1}/mo vs ${price2}/mo. "
        "SLA: {sla1} vs {sla2}. Decision: Going with {vendor1} due to {reason}.",

        "The quarterly business review highlighted several areas for improvement. Sales pipeline is at ${amount}M. "
        "We need to increase lead generation by {percent}% to hit annual targets.",

        "Employee performance review: {person} has exceeded expectations in {area}. Areas for development: "
        "{area2}. Promotion recommendation: {recommendation}. Compensation adjustment: {percent}%.",

        "Risk assessment for {project}: Technical risk is {level}. Timeline risk is {level2}. "
        "Financial risk is {level3}. Mitigation: {mitigation}. Contingency budget: ${amount}K.",
    ]

    fill_values = {
        'system': ['CRM', 'ERP', 'database', 'analytics platform', 'email system', 'CI/CD pipeline'],
        'platform': ['AWS', 'Azure', 'GCP', 'Kubernetes', 'Salesforce', 'Snowflake'],
        'reason': ['better scalability', 'cost reduction', 'compliance requirements', 'performance issues'],
        'date': ['January 15', 'Q2 2026', 'March 1st', 'next sprint', 'end of month'],
        'date2': ['Friday', 'next Monday', 'end of week'],
        'amount': ['50', '100', '250', '500', '1000', '2000'],
        'amount2': ['30', '75', '150', '300'],
        'amount3': ['20', '50', '100', '200'],
        'topic': ['roadmap priorities', 'hiring plan', 'Q3 strategy', 'vendor contract renewal'],
        'decision1': ['Adopt new tool', 'Restructure team', 'Increase budget', 'Delay launch'],
        'decision2': ['hire 3 engineers', 'cancel legacy project', 'extend timeline 2 weeks'],
        'person': ['Sarah', 'Mike', 'the PM team', 'David', 'Lisa', 'the engineering lead'],
        'manager': ['John', 'Sarah', 'Rachel', 'Mark'],
        'quarter': ['1', '2', '3', '4'],
        'status': ['exceeded', 'met', 'missed by 5%', 'on track'],
        'score': ['7.5', '8.2', '6.8', '9.1'],
        'percent': ['15', '20', '30', '45', '10', '25'],
        'risk': ['supply chain delays', 'key person dependency', 'market volatility'],
        'cause': ['memory leak', 'database connection pool exhaustion', 'expired certificate'],
        'impact': ['2 hours downtime', '500 users affected', 'delayed deployment'],
        'resolution': ['rolled back deployment', 'increased pool size', 'renewed certificate'],
        'project': ['Project Alpha', 'Phase 2 migration', 'Customer Portal v2', 'Data Lake'],
        'milestone': ['MVP complete', 'API integration done', 'UAT started'],
        'blocker': ['waiting on legal review', 'dependency on Team B', 'infrastructure provisioning'],
        'role': ['Software Engineer', 'Product Manager', 'Data Analyst', 'DevOps Engineer'],
        'training': ['security awareness', 'code review guidelines', 'agile methodology'],
        'document': ['architecture docs', 'coding standards', 'team handbook'],
        'capex': ['50', '100', '200'],
        'item': ['servers', 'licenses', 'office expansion'],
        'count': ['15', '50', '100', '200', '500', '1000'],
        'issue1': ['slow load times', 'login failures', 'data sync errors'],
        'issue2': ['missing features', 'UI confusion', 'mobile responsiveness'],
        'strategy': ['improved onboarding', 'premium support tier', 'feature parity'],
        'feature': ['real-time collaboration', 'advanced analytics', 'SSO integration'],
        'month': ['March', 'April', 'May', 'June'],
        'vendor1': ['Datadog', 'Stripe', 'Twilio', 'SendGrid'],
        'vendor2': ['New Relic', 'Square', 'Vonage', 'Mailgun'],
        'service': ['monitoring', 'payments', 'communications', 'email delivery'],
        'price1': ['500', '1000', '2000'],
        'price2': ['700', '1500', '2500'],
        'sla1': ['99.9%', '99.95%', '99.99%'],
        'sla2': ['99.5%', '99.9%', '99.95%'],
        'area': ['technical leadership', 'project delivery', 'team collaboration'],
        'area2': ['public speaking', 'documentation', 'cross-team communication'],
        'recommendation': ['promote to senior', 'extend probation', 'lateral move'],
        'level': ['high', 'medium', 'low'],
        'level2': ['medium', 'high', 'low'],
        'level3': ['low', 'medium', 'high'],
        'mitigation': ['weekly risk reviews', 'additional resources', 'phased rollout'],
    }

    texts = []
    for _ in range(2000):
        template = random.choice(templates)
        text = template
        for key, values in fill_values.items():
            placeholder = '{' + key + '}'
            while placeholder in text:
                text = text.replace(placeholder, random.choice(values), 1)
        texts.append(text)

    return texts


def train_content_classifier() -> Optional[str]:
    """
    Train a binary classifier: protocol vs business content.

    Uses TF-IDF features + LogisticRegression.
    Returns path to saved model or None if training fails.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import cross_val_score
        from sklearn.pipeline import Pipeline
        import joblib
    except ImportError:
        logger.error('[Trainer] scikit-learn not installed, skipping classifier training')
        return None

    # Load data
    protocol_texts = _load_protocol_texts()
    business_texts = _generate_business_texts()

    if len(protocol_texts) < 50:
        logger.warning(f'[Trainer] Only {len(protocol_texts)} protocol texts, need more for reliable training')
        # Use seed protocol examples if corpus is too small
        protocol_texts.extend(_generate_seed_protocol_texts())

    # Balance classes
    min_size = min(len(protocol_texts), len(business_texts))
    if min_size < 100:
        logger.warning(f'[Trainer] Very small dataset ({min_size}), classifier may be unreliable')

    random.shuffle(protocol_texts)
    random.shuffle(business_texts)
    protocol_texts = protocol_texts[:min_size]
    business_texts = business_texts[:min_size]

    texts = protocol_texts + business_texts
    labels = [1] * len(protocol_texts) + [0] * len(business_texts)

    # Shuffle
    combined = list(zip(texts, labels))
    random.shuffle(combined)
    texts, labels = zip(*combined)
    texts, labels = list(texts), list(labels)

    logger.info(f'[Trainer] Training content classifier: {len(texts)} samples '
                f'({sum(labels)} protocol, {len(labels) - sum(labels)} business)')

    # Build pipeline
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=10000,
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.95,
            sublinear_tf=True,
        )),
        ('clf', LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight='balanced',
            solver='lbfgs',
        )),
    ])

    # Cross-validate
    scores = cross_val_score(pipeline, texts, labels, cv=5, scoring='accuracy')
    logger.info(f'[Trainer] Content classifier CV accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})')

    # Train on full data
    pipeline.fit(texts, labels)

    # Save
    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(pipeline, CONTENT_CLASSIFIER_PATH)
    logger.info(f'[Trainer] Saved content classifier to {CONTENT_CLASSIFIER_PATH}')

    return CONTENT_CLASSIFIER_PATH


def train_missing_step_detector() -> Optional[str]:
    """
    Train a classifier to detect if a step is missing between two consecutive steps.

    Uses BioProtocolBench step ordering data.
    Returns path to saved model or None.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.ensemble import GradientBoostingClassifier
        from sklearn.model_selection import cross_val_score
        from sklearn.pipeline import Pipeline
        import joblib
    except ImportError:
        logger.error('[Trainer] scikit-learn not installed')
        return None

    # Load BioProtocolBench training data
    training_file = os.path.join(CORPUS_DIR, 'bioprotocolbench_training.json')
    if not os.path.exists(training_file):
        logger.warning('[Trainer] BioProtocolBench training data not found')
        return None

    with open(training_file, 'r') as f:
        training_data = json.load(f)

    ordering_data = training_data.get('training', {}).get('step_ordering', [])
    if len(ordering_data) < 100:
        logger.warning(f'[Trainer] Only {len(ordering_data)} step ordering instances, need more')
        return None

    # Build training pairs: consecutive steps → missing or not
    texts = []
    labels = []

    for instance in ordering_data[:5000]:
        steps = instance.get('steps', instance.get('input', ''))
        if isinstance(steps, list):
            # Correct order = no missing step (label 0)
            for i in range(len(steps) - 1):
                s1 = str(steps[i]) if not isinstance(steps[i], str) else steps[i]
                s2 = str(steps[i + 1]) if not isinstance(steps[i + 1], str) else steps[i + 1]
                pair_text = f"{s1} [SEP] {s2}"
                texts.append(pair_text[:1000])
                labels.append(0)

                # Create synthetic missing step (skip one)
                if i + 2 < len(steps):
                    s3 = str(steps[i + 2]) if not isinstance(steps[i + 2], str) else steps[i + 2]
                    pair_text_missing = f"{s1} [SEP] {s3}"
                    texts.append(pair_text_missing[:1000])
                    labels.append(1)

    if len(texts) < 100:
        logger.warning('[Trainer] Not enough step pairs for training')
        return None

    logger.info(f'[Trainer] Training missing step detector: {len(texts)} pairs '
                f'({sum(labels)} missing, {len(labels) - sum(labels)} consecutive)')

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=8000,
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
        )),
        ('clf', GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            subsample=0.8,
        )),
    ])

    scores = cross_val_score(pipeline, texts, labels, cv=3, scoring='accuracy')
    logger.info(f'[Trainer] Missing step detector CV accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})')

    pipeline.fit(texts, labels)

    joblib.dump(pipeline, MISSING_STEP_PATH)
    logger.info(f'[Trainer] Saved missing step detector to {MISSING_STEP_PATH}')

    return MISSING_STEP_PATH


def train_completeness_scorer() -> Optional[str]:
    """
    Train a regressor to score protocol completeness (0-1).

    Uses corpus protocols with completeness heuristic as labels.
    Returns path to saved model or None.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import cross_val_score
        from sklearn.pipeline import Pipeline
        import joblib
    except ImportError:
        logger.error('[Trainer] scikit-learn not installed')
        return None

    # Load protocols and compute completeness heuristic
    filepath = os.path.join(CORPUS_DIR, 'unified_corpus.jsonl')
    if not os.path.exists(filepath):
        logger.warning('[Trainer] Unified corpus not found')
        return None

    texts = []
    scores = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                p = json.loads(line)
            except json.JSONDecodeError:
                continue

            text = p.get('raw_text', '')
            if len(text) < 50:
                continue

            # Compute completeness heuristic (0-1)
            score = 0.0
            checks = 0
            total = 0

            # Has steps?
            total += 1
            if p.get('steps') and len(p['steps']) >= 3:
                checks += 1

            # Has reagents?
            total += 1
            if p.get('reagents') and len(p['reagents']) >= 1:
                checks += 1

            # Has equipment?
            total += 1
            if p.get('equipment') and len(p['equipment']) >= 1:
                checks += 1

            # Has safety notes?
            total += 1
            if p.get('safety_notes') and len(p['safety_notes']) >= 1:
                checks += 1

            # Steps have action verbs?
            total += 1
            steps_with_verbs = sum(1 for s in p.get('steps', []) if s.get('action_verb'))
            if steps_with_verbs > 0:
                checks += 1

            # Has parameters in text?
            total += 1
            if re.search(r'\d+\s*(?:mM|µM|uM|mg/ml|ml|µl|min|sec|°C|rpm)', text):
                checks += 1

            # Has title?
            total += 1
            if p.get('title') and len(p['title']) > 10:
                checks += 1

            score = checks / max(total, 1)
            texts.append(text[:5000])
            scores.append(score)

    if len(texts) < 100:
        logger.warning(f'[Trainer] Only {len(texts)} protocols for completeness scoring')
        return None

    logger.info(f'[Trainer] Training completeness scorer: {len(texts)} protocols')

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(
            max_features=8000,
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
        )),
        ('reg', GradientBoostingRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            subsample=0.8,
        )),
    ])

    cv_scores = cross_val_score(pipeline, texts, scores, cv=3, scoring='r2')
    logger.info(f'[Trainer] Completeness scorer CV R²: {cv_scores.mean():.3f} (+/- {cv_scores.std():.3f})')

    pipeline.fit(texts, scores)

    joblib.dump(pipeline, COMPLETENESS_PATH)
    logger.info(f'[Trainer] Saved completeness scorer to {COMPLETENESS_PATH}')

    return COMPLETENESS_PATH


def _generate_seed_protocol_texts() -> List[str]:
    """Generate seed protocol texts if corpus is too small."""
    return [
        "1. Pipette 10 µL of sample into a 1.5 mL microcentrifuge tube. 2. Add 90 µL of PBS buffer. "
        "3. Vortex for 10 seconds. 4. Centrifuge at 12,000 rpm for 5 minutes at 4°C. "
        "5. Carefully aspirate the supernatant. 6. Resuspend the pellet in 50 µL of lysis buffer.",

        "Prepare a 1% agarose gel by dissolving 1 g of agarose in 100 mL of 1X TAE buffer. "
        "Microwave for 2 minutes until dissolved. Cool to 55°C and add 5 µL of ethidium bromide. "
        "Pour into gel mold and insert comb. Allow to solidify for 30 minutes at room temperature.",

        "Cell culture protocol: Thaw cells rapidly in a 37°C water bath. Transfer to 10 mL of pre-warmed "
        "DMEM + 10% FBS. Centrifuge at 300 xg for 5 minutes. Aspirate supernatant and resuspend in "
        "fresh medium. Seed at 1 × 10^6 cells per 10 cm dish. Incubate at 37°C, 5% CO2.",

        "Western blot: Load 20 µg of protein per lane on a 10% SDS-PAGE gel. Run at 120V for 90 minutes. "
        "Transfer to PVDF membrane at 100V for 1 hour. Block with 5% milk in TBST for 1 hour. "
        "Incubate with primary antibody (1:1000) overnight at 4°C. Wash 3× with TBST.",

        "PCR amplification: Set up 50 µL reaction: 25 µL 2X master mix, 2 µL forward primer (10 µM), "
        "2 µL reverse primer (10 µM), 1 µL template DNA (50 ng), 20 µL nuclease-free water. "
        "Cycling: 95°C 3 min, then 35 cycles of 95°C 30s, 58°C 30s, 72°C 1 min. Final extension 72°C 5 min.",

        "RNA extraction using TRIzol: Add 1 mL TRIzol per 10^7 cells. Caution: perform in fume hood. "
        "Incubate 5 min at RT. Add 200 µL chloroform, shake vigorously for 15 sec. "
        "Centrifuge 12,000 xg for 15 min at 4°C. Transfer aqueous phase to new tube.",

        "ELISA protocol: Coat 96-well plate with 100 µL capture antibody (2 µg/mL in carbonate buffer) "
        "overnight at 4°C. Wash 3× with PBST. Block with 200 µL 1% BSA for 2 hours at RT. "
        "Add 100 µL samples and standards. Incubate 2 hours at RT.",

        "Immunofluorescence staining: Fix cells with 4% PFA for 15 minutes at room temperature. "
        "Permeabilize with 0.1% Triton X-100 in PBS for 10 minutes. Block with 5% normal goat serum "
        "for 1 hour. Incubate with primary antibody (1:200) overnight at 4°C.",

        "Bacterial transformation: Thaw competent cells on ice for 30 minutes. Add 1 µL plasmid DNA "
        "(1-10 ng). Incubate on ice for 30 minutes. Heat shock at 42°C for 45 seconds. "
        "Return to ice for 2 minutes. Add 950 µL SOC medium. Shake at 37°C for 1 hour at 225 rpm.",

        "HPLC sample preparation: Dissolve 10 mg of compound in 1 mL HPLC-grade methanol. "
        "Filter through 0.22 µm PVDF syringe filter. Transfer to HPLC vial. "
        "Injection volume: 10 µL. Column: C18, 250 × 4.6 mm, 5 µm. Mobile phase: 60:40 ACN:water.",
    ] * 20  # Repeat to get 200 samples


def train_all() -> Dict[str, Optional[str]]:
    """Train all classifiers and return paths to saved models."""
    results = {}

    logger.info('[Trainer] Starting classifier training...')

    results['content_classifier'] = train_content_classifier()
    results['missing_step_detector'] = train_missing_step_detector()
    results['completeness_scorer'] = train_completeness_scorer()

    successful = sum(1 for v in results.values() if v is not None)
    logger.info(f'[Trainer] Training complete: {successful}/{len(results)} models trained')

    return results


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    results = train_all()
    print(f'\nTraining results:')
    for name, path in results.items():
        status = f'Saved to {path}' if path else 'FAILED'
        print(f'  {name}: {status}')
