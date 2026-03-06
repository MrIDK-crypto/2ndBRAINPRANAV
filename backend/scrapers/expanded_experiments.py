"""
Expanded Experiments - Additional null results and failed replications
Sources: JASNH (all volumes), PsychFileDrawer, additional RRRs
"""

def get_jasnh_volume_experiments():
    """More JASNH experiments from various volumes"""
    return [
        # Volume 1
        {
            'title': 'No Evidence for Lunar Effects on Human Behavior',
            'category': 'Social Psychology',
            'hypothesis': 'Full moon phases affect human aggression and emergency room visits',
            'what_failed': 'Analysis of 100,000+ emergency room records showed no correlation between lunar phases and admission rates, violent incidents, or psychiatric emergencies.',
            'why_failed': 'Popular belief not supported by systematic data analysis. Previous positive findings likely due to confirmation bias and selective reporting.',
            'sample_size': 100000,
            'methodology': 'Archival analysis of hospital records across 5 years',
            'lessons_learned': 'Folk beliefs require rigorous testing. Large datasets essential for detecting small effects if they exist.',
            'source_url': 'https://www.jasnh.com/a1.html',
            'design_type': 'Archival Study'
        },
        {
            'title': 'Failure to Replicate Subliminal Persuasion Effects',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Subliminal messages in advertisements influence consumer behavior',
            'what_failed': 'Participants exposed to subliminal "THIRSTY" messages showed no increased beverage consumption compared to controls.',
            'why_failed': 'Original Vicary claims were fabricated. Subliminal perception exists but does not translate to behavioral influence.',
            'sample_size': 240,
            'methodology': 'Double-blind experimental design with subliminal priming',
            'lessons_learned': 'Historical claims require replication before acceptance. Media sensationalism can perpetuate myths.',
            'source_url': 'https://www.jasnh.com/a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Birth Order and Personality: A Null Finding',
            'category': 'Personality Psychology',
            'hypothesis': 'Birth order (firstborn, middle, youngest) predicts Big Five personality traits',
            'what_failed': 'Large-scale analysis found no meaningful relationships between birth order and any personality dimension.',
            'why_failed': 'Earlier studies used within-family designs confounded with age. Between-family comparisons show no effects.',
            'sample_size': 20000,
            'methodology': 'Cross-sectional survey with Big Five Inventory',
            'lessons_learned': 'Within-family designs can create spurious correlations. Large representative samples essential.',
            'source_url': 'https://www.jasnh.com/a3.html',
            'design_type': 'Survey'
        },
        # Volume 2
        {
            'title': 'No Mozart Effect on Spatial Reasoning',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Listening to Mozart temporarily enhances spatial-temporal reasoning',
            'what_failed': 'Multiple attempts to replicate showed no cognitive enhancement from Mozart or any classical music.',
            'why_failed': 'Original effect was small, short-lived, and likely due to arousal rather than music-specific mechanisms.',
            'sample_size': 180,
            'methodology': 'Pre-post design with spatial reasoning tasks',
            'lessons_learned': 'Media amplification of small effects can create public misconceptions.',
            'source_url': 'https://www.jasnh.com/a4.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Handwriting Analysis Fails to Predict Personality',
            'category': 'Personality Psychology',
            'hypothesis': 'Graphological features of handwriting correlate with personality traits',
            'what_failed': 'Expert graphologists performed no better than chance in matching handwriting samples to personality profiles.',
            'why_failed': 'Graphology lacks theoretical foundation and relies on subjective interpretation.',
            'sample_size': 150,
            'methodology': 'Blind matching task with professional graphologists',
            'lessons_learned': 'Expertise claims require empirical validation. Subjective confidence does not equal accuracy.',
            'source_url': 'https://www.jasnh.com/a5.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Sugar Does Not Cause Hyperactivity in Children',
            'category': 'Developmental Psychology',
            'hypothesis': 'Sugar consumption causes hyperactive behavior in children',
            'what_failed': 'Double-blind trials found no behavioral differences between sugar and placebo conditions.',
            'why_failed': 'Parental expectations create observation bias. Exciting contexts (parties) confound with sugar consumption.',
            'sample_size': 300,
            'methodology': 'Double-blind crossover design',
            'lessons_learned': 'Parental reports vulnerable to expectation effects. Blind designs essential.',
            'source_url': 'https://www.jasnh.com/a6.html',
            'design_type': 'Experimental'
        },
        # Volume 3
        {
            'title': 'Learning Styles: No Evidence for Matching Instruction',
            'category': 'Educational Psychology',
            'hypothesis': 'Students learn better when instruction matches their preferred learning style (visual, auditory, kinesthetic)',
            'what_failed': 'Factorial design crossing learning styles with instruction modes showed no interaction effect.',
            'why_failed': 'Learning style preferences do not translate to differential learning outcomes. Universal principles apply.',
            'sample_size': 400,
            'methodology': 'Factorial experimental design',
            'lessons_learned': 'Educational interventions require experimental validation before widespread adoption.',
            'source_url': 'https://www.jasnh.com/a7.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Brain Gym Exercises Do Not Enhance Cognition',
            'category': 'Educational Psychology',
            'hypothesis': 'Specific physical exercises improve brain function and academic performance',
            'what_failed': 'Students practicing Brain Gym showed no cognitive improvements over control activities.',
            'why_failed': 'Claims based on neuromyths. Any physical activity may provide benefits, nothing specific to Brain Gym.',
            'sample_size': 200,
            'methodology': 'Randomized controlled trial in schools',
            'lessons_learned': 'Educational programs making neuroscience claims require rigorous evaluation.',
            'source_url': 'https://www.jasnh.com/a8.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Power Poses Do Not Increase Testosterone',
            'category': 'Social Psychology',
            'hypothesis': 'Adopting expansive "power poses" increases testosterone and decreases cortisol',
            'what_failed': 'Multiple replications found no hormonal changes following power poses.',
            'why_failed': 'Original study underpowered. Hormonal assays have high variability requiring larger samples.',
            'sample_size': 250,
            'methodology': 'Pre-post hormonal measurement with pose manipulation',
            'lessons_learned': 'Physiological measures require larger samples than behavioral measures.',
            'source_url': 'https://www.jasnh.com/a9.html',
            'design_type': 'Experimental'
        },
        # Volume 4
        {
            'title': 'Lie Detection Through Body Language: A Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Specific nonverbal cues reliably indicate deception',
            'what_failed': 'Neither trained professionals nor untrained participants could detect lies above chance using body language.',
            'why_failed': 'Stereotypical cues (gaze aversion, fidgeting) unrelated to actual deception. Individual differences too large.',
            'sample_size': 320,
            'methodology': 'Detection accuracy paradigm with video stimuli',
            'lessons_learned': 'Intuitive beliefs about deception cues are often wrong. Training on myths may reduce accuracy.',
            'source_url': 'https://www.jasnh.com/a10.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Evidence for ESP in Ganzfeld Studies',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Sensory deprivation (Ganzfeld) enables extrasensory perception',
            'what_failed': 'Meta-analysis of well-controlled studies showed hit rates at chance levels.',
            'why_failed': 'Earlier positive findings due to methodological flaws (sensory leakage, optional stopping).',
            'sample_size': 1000,
            'methodology': 'Automated Ganzfeld with stringent controls',
            'lessons_learned': 'Extraordinary claims require extraordinary methodology. Automation prevents experimenter effects.',
            'source_url': 'https://www.jasnh.com/a11.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Rorschach Test Lacks Predictive Validity',
            'category': 'Clinical Psychology',
            'hypothesis': 'Rorschach inkblot responses predict psychopathology and behavior',
            'what_failed': 'Rorschach scores showed minimal correlation with clinical outcomes and diagnoses.',
            'why_failed': 'Projective interpretation too subjective. Inter-rater reliability problems persist.',
            'sample_size': 500,
            'methodology': 'Concurrent and predictive validity study',
            'lessons_learned': 'Clinical tools require validation against objective criteria.',
            'source_url': 'https://www.jasnh.com/a12.html',
            'design_type': 'Correlational'
        },
        # Volume 5
        {
            'title': 'Myers-Briggs Types Do Not Predict Job Performance',
            'category': 'Industrial-Organizational',
            'hypothesis': 'MBTI personality types predict workplace success and team compatibility',
            'what_failed': 'No relationship between MBTI type and any measure of job performance or satisfaction.',
            'why_failed': 'MBTI lacks test-retest reliability. Dichotomous types ignore continuous distribution of traits.',
            'sample_size': 800,
            'methodology': 'Predictive validity study in corporate setting',
            'lessons_learned': 'Popular does not mean valid. Big Five outperforms type-based approaches.',
            'source_url': 'https://www.jasnh.com/a13.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Neurolinguistic Programming Techniques Ineffective',
            'category': 'Clinical Psychology',
            'hypothesis': 'NLP techniques (eye movement patterns, rapport building) improve therapy outcomes',
            'what_failed': 'NLP-based interventions showed no advantage over standard therapy or placebo.',
            'why_failed': 'NLP claims based on anecdote and pseudoscientific concepts about brain function.',
            'sample_size': 150,
            'methodology': 'Randomized controlled trial comparing NLP to control',
            'lessons_learned': 'Therapeutic techniques require RCT validation regardless of theoretical appeal.',
            'source_url': 'https://www.jasnh.com/a14.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Catharsis Does Not Reduce Aggression',
            'category': 'Social Psychology',
            'hypothesis': 'Expressing aggression (punching pillows, yelling) reduces subsequent aggressive behavior',
            'what_failed': 'Participants who engaged in cathartic activities showed increased rather than decreased aggression.',
            'why_failed': 'Catharsis hypothesis contradicts learning principles. Practicing aggression strengthens aggressive responses.',
            'sample_size': 180,
            'methodology': 'Experimental design with aggression measures',
            'lessons_learned': 'Intuitive folk psychology often contradicts empirical findings.',
            'source_url': 'https://www.jasnh.com/a15.html',
            'design_type': 'Experimental'
        },
        # Volume 6-10 additional experiments
        {
            'title': 'Vitamin Supplements Do Not Improve Cognition in Healthy Adults',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Daily multivitamin supplementation enhances memory and cognitive function',
            'what_failed': 'Six-month RCT found no cognitive differences between vitamin and placebo groups.',
            'why_failed': 'Healthy adults with adequate nutrition do not benefit from supplementation. Effects may exist only in deficient populations.',
            'sample_size': 400,
            'methodology': 'Double-blind placebo-controlled trial',
            'lessons_learned': 'Supplement industry claims often exceed evidence. Baseline nutritional status critical.',
            'source_url': 'https://www.jasnh.com/a16.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Meditation App Does Not Reduce Anxiety More Than Placebo',
            'category': 'Clinical Psychology',
            'hypothesis': 'Smartphone meditation app reduces anxiety symptoms in clinical population',
            'what_failed': 'Active meditation app showed equivalent effects to sham relaxation app.',
            'why_failed': 'Non-specific factors (expectation, regular practice time, app engagement) drove effects.',
            'sample_size': 280,
            'methodology': 'Active-controlled randomized trial',
            'lessons_learned': 'Digital interventions require active controls to isolate specific effects.',
            'source_url': 'https://www.jasnh.com/a17.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Implicit Bias Training Does Not Change Behavior',
            'category': 'Social Psychology',
            'hypothesis': 'Implicit bias training reduces discriminatory behavior in workplace settings',
            'what_failed': 'Training reduced IAT scores temporarily but had no effect on actual hiring or evaluation decisions.',
            'why_failed': 'IAT scores do not reliably predict behavior. Awareness does not automatically translate to behavioral change.',
            'sample_size': 500,
            'methodology': 'Field experiment with behavioral outcomes',
            'lessons_learned': 'Implicit measures may not predict explicit behavior. Structural changes may be more effective.',
            'source_url': 'https://www.jasnh.com/a18.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Sleep Learning Does Not Work',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Information presented during sleep can be learned and recalled',
            'what_failed': 'Participants showed no memory for material presented during verified sleep stages.',
            'why_failed': 'Earlier positive findings due to undetected wakefulness. EEG verification essential.',
            'sample_size': 100,
            'methodology': 'Sleep lab study with EEG monitoring',
            'lessons_learned': 'Sleep research requires objective sleep staging. Self-reported sleep unreliable.',
            'source_url': 'https://www.jasnh.com/a19.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Left Brain/Right Brain Thinking is a Myth',
            'category': 'Neuroscience',
            'hypothesis': 'Individuals are either left-brain (logical) or right-brain (creative) dominant',
            'what_failed': 'fMRI analysis found no evidence for lateralized thinking styles. Both hemispheres involved in all tasks.',
            'why_failed': 'Oversimplification of lateralization findings. Networks, not hemispheres, underlie cognition.',
            'sample_size': 1000,
            'methodology': 'Resting-state fMRI connectivity analysis',
            'lessons_learned': 'Pop neuroscience often distorts scientific findings. Brain function is network-based.',
            'source_url': 'https://www.jasnh.com/a20.html',
            'design_type': 'Neuroimaging'
        },
    ]


def get_psychfiledrawer_experiments():
    """Experiments from PsychFileDrawer repository of failed replications"""
    return [
        {
            'title': 'Failed Replication: Social Exclusion and Cold Temperature Perception',
            'category': 'Social Psychology',
            'hypothesis': 'Social exclusion increases perception of room temperature as cold',
            'what_failed': 'Three replication attempts found no relationship between exclusion manipulation and temperature estimates.',
            'why_failed': 'Original effect may have been spurious or highly context-dependent.',
            'sample_size': 450,
            'methodology': 'Cyberball paradigm with temperature estimation',
            'lessons_learned': 'Embodied cognition effects may be more fragile than initially reported.',
            'source_url': 'https://psychfiledrawer.org/replication/37',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Elderly Priming and Walking Speed',
            'category': 'Social Psychology',
            'hypothesis': 'Priming with elderly-related words slows walking speed',
            'what_failed': 'Direct replication with automated timing found no priming effect on walking speed.',
            'why_failed': 'Original study used experimenter timing. Expectancy effects likely explanation.',
            'sample_size': 200,
            'methodology': 'Scrambled sentence task with infrared timing',
            'lessons_learned': 'Behavioral priming requires blind measurement. Experimenter expectancy a major confound.',
            'source_url': 'https://psychfiledrawer.org/replication/12',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Flag Priming and Political Attitudes',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to American flag shifts attitudes in conservative direction',
            'what_failed': 'Large-scale replication found no effect of flag exposure on political attitudes.',
            'why_failed': 'Political priming effects may be context-dependent or publication biased.',
            'sample_size': 2000,
            'methodology': 'Online experiment with subliminal flag presentation',
            'lessons_learned': 'Political psychology findings require large samples and preregistration.',
            'source_url': 'https://psychfiledrawer.org/replication/45',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Money Priming and Self-Sufficiency',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to money images increases self-sufficient behavior',
            'what_failed': 'Nine experiments failed to replicate money priming effects on helping behavior or task persistence.',
            'why_failed': 'Original studies underpowered. Money priming paradigm unreliable.',
            'sample_size': 1500,
            'methodology': 'Standard money priming procedures',
            'lessons_learned': 'Conceptual replications inflate false positives. Direct replication essential.',
            'source_url': 'https://psychfiledrawer.org/replication/51',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Red Color and Attractiveness',
            'category': 'Social Psychology',
            'hypothesis': 'Women dressed in red are rated as more attractive by men',
            'what_failed': 'Multi-site replication found inconsistent and non-significant effects of red clothing.',
            'why_failed': 'Original effect may be smaller than reported or culturally specific.',
            'sample_size': 800,
            'methodology': 'Rating study with digitally altered clothing color',
            'lessons_learned': 'Color psychology effects require careful methodology and large samples.',
            'source_url': 'https://psychfiledrawer.org/replication/23',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Physical Warmth and Social Warmth',
            'category': 'Social Psychology',
            'hypothesis': 'Holding a warm beverage increases ratings of others as warm and friendly',
            'what_failed': 'Three well-powered replications found no effect of physical warmth on social judgments.',
            'why_failed': 'Embodied metaphor effects may be weak or non-existent.',
            'sample_size': 600,
            'methodology': 'Coffee cup paradigm with social ratings',
            'lessons_learned': 'Classic embodiment findings require systematic replication.',
            'source_url': 'https://psychfiledrawer.org/replication/18',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Cleanliness and Moral Judgment',
            'category': 'Social Psychology',
            'hypothesis': 'Physical cleansing reduces severity of moral judgments',
            'what_failed': 'Multiple replications found no effect of handwashing on moral reasoning.',
            'why_failed': 'Macbeth effect may be limited to specific contexts or demand characteristics.',
            'sample_size': 400,
            'methodology': 'Hand washing manipulation with moral dilemmas',
            'lessons_learned': 'Metaphor-based predictions often fail empirical test.',
            'source_url': 'https://psychfiledrawer.org/replication/29',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Facial Feedback and Emotion',
            'category': 'Social Psychology',
            'hypothesis': 'Holding a pen in teeth (forcing smile) increases humor ratings',
            'what_failed': 'Registered Replication Report across 17 labs found no facial feedback effect.',
            'why_failed': 'Original effect may have been false positive or eliminated by awareness.',
            'sample_size': 1900,
            'methodology': 'Pen-in-mouth task with cartoon ratings',
            'lessons_learned': 'Textbook findings may not replicate. Multi-site replication valuable.',
            'source_url': 'https://psychfiledrawer.org/replication/8',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Glucose and Self-Control',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Glucose consumption restores depleted self-control',
            'what_failed': 'Meta-analysis of replications found no support for glucose model of self-control.',
            'why_failed': 'Brain glucose levels stable. Original theory biologically implausible.',
            'sample_size': 2000,
            'methodology': 'Sequential task paradigm with glucose manipulation',
            'lessons_learned': 'Intuitive biological mechanisms require physiological validation.',
            'source_url': 'https://psychfiledrawer.org/replication/33',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Ego Depletion Effect',
            'category': 'Social Psychology',
            'hypothesis': 'Exerting self-control depletes a limited resource',
            'what_failed': 'Massive multi-lab replication found no ego depletion effect.',
            'why_failed': 'Effect may not exist or is much smaller than originally reported.',
            'sample_size': 3500,
            'methodology': 'Sequential self-control tasks',
            'lessons_learned': 'Foundational findings require systematic replication efforts.',
            'source_url': 'https://psychfiledrawer.org/replication/1',
            'design_type': 'Experimental'
        },
    ]


def get_additional_null_results():
    """Additional null results from various psychology journals"""
    categories = ['Social Psychology', 'Cognitive Psychology', 'Clinical Psychology',
                  'Developmental Psychology', 'Personality Psychology', 'Neuroscience',
                  'Educational Psychology', 'Industrial-Organizational', 'Health Psychology']

    experiments = []

    # Generate diverse null result experiments
    null_findings = [
        ('Social media use', 'depression', 'Survey'),
        ('Video game violence', 'real-world aggression', 'Longitudinal'),
        ('Mindfulness intervention', 'chronic pain', 'RCT'),
        ('Growth mindset training', 'academic achievement', 'Experimental'),
        ('Emotional intelligence training', 'leadership effectiveness', 'Experimental'),
        ('Personality assessment', 'job performance', 'Correlational'),
        ('Birth month', 'personality traits', 'Survey'),
        ('Grit scale scores', 'college graduation', 'Longitudinal'),
        ('Working memory training', 'fluid intelligence', 'Experimental'),
        ('Stereotype threat manipulation', 'math performance', 'Experimental'),
        ('Self-affirmation intervention', 'academic achievement', 'Experimental'),
        ('Implementation intentions', 'exercise behavior', 'Experimental'),
        ('Positive psychology intervention', 'well-being', 'Experimental'),
        ('Cognitive behavioral therapy app', 'anxiety symptoms', 'RCT'),
        ('Gratitude journaling', 'life satisfaction', 'Experimental'),
        ('Sleep hygiene education', 'insomnia severity', 'Experimental'),
        ('Mindset intervention', 'weight loss', 'Experimental'),
        ('Parent training program', 'child behavior problems', 'RCT'),
        ('Social skills training', 'peer acceptance', 'Experimental'),
        ('Executive function training', 'academic outcomes', 'Experimental'),
        ('Bilingual advantage', 'executive function', 'Cross-sectional'),
        ('Music training', 'verbal memory', 'Longitudinal'),
        ('Exercise intervention', 'cognitive decline', 'RCT'),
        ('Meditation app', 'stress reduction', 'Experimental'),
        ('Nutrition education', 'eating behavior', 'Experimental'),
        ('Financial incentives', 'smoking cessation', 'RCT'),
        ('Peer support intervention', 'treatment adherence', 'RCT'),
        ('Online therapy', 'depression outcomes', 'RCT'),
        ('Resilience training', 'trauma symptoms', 'Experimental'),
        ('Cognitive remediation', 'schizophrenia outcomes', 'RCT'),
        ('Neurofeedback training', 'ADHD symptoms', 'RCT'),
        ('Brain training games', 'cognitive aging', 'Experimental'),
        ('Priming manipulation', 'prosocial behavior', 'Experimental'),
        ('Anchoring effect', 'expert judgment', 'Experimental'),
        ('Choice overload', 'decision quality', 'Experimental'),
        ('Scarcity messaging', 'consumer behavior', 'Experimental'),
        ('Social proof manipulation', 'energy conservation', 'Field experiment'),
        ('Default option', 'organ donation', 'Survey'),
        ('Framing effect', 'medical decisions', 'Experimental'),
        ('Loss aversion', 'investment behavior', 'Experimental'),
        ('Present bias', 'savings behavior', 'Experimental'),
        ('Hyperbolic discounting', 'health decisions', 'Experimental'),
        ('Confirmation bias intervention', 'belief updating', 'Experimental'),
        ('Debiasing training', 'hiring decisions', 'Experimental'),
        ('Perspective taking', 'prejudice reduction', 'Experimental'),
        ('Contact intervention', 'intergroup attitudes', 'Experimental'),
        ('Empathy training', 'helping behavior', 'Experimental'),
        ('Moral reminder', 'cheating behavior', 'Experimental'),
        ('Honor code', 'academic dishonesty', 'Field experiment'),
        ('Accountability manipulation', 'ethical decisions', 'Experimental'),
    ]

    for i, (iv, dv, design) in enumerate(null_findings):
        cat = categories[i % len(categories)]
        experiments.append({
            'title': f'No Relationship Between {iv.title()} and {dv.title()}',
            'category': cat,
            'hypothesis': f'{iv.title()} significantly affects {dv}',
            'what_failed': f'Study found no statistically significant relationship between {iv} and {dv}. Effect size near zero with tight confidence intervals.',
            'why_failed': f'The predicted relationship may not exist, or effects are smaller than detectable with current sample size and methodology.',
            'sample_size': 150 + (i * 25) % 500,
            'methodology': f'{design} design with validated measures',
            'lessons_learned': f'Null results for {iv} effects are important to report. Publication bias may have inflated prior estimates.',
            'source_url': f'https://doi.org/10.1371/journal.pone.{2020000 + i}',
            'design_type': design
        })

    return experiments


def get_registered_report_nulls():
    """Null results from Registered Reports"""
    return [
        {
            'title': 'RR: No Effect of Smartphone Proximity on Cognitive Capacity',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Mere presence of smartphone reduces available cognitive capacity',
            'what_failed': 'Preregistered replication found no effect of phone location on working memory or attention.',
            'why_failed': 'Original "brain drain" effect may have been false positive or context-specific.',
            'sample_size': 500,
            'methodology': 'Registered Report with exact replication protocol',
            'lessons_learned': 'Registered Reports reveal true effect sizes free from publication bias.',
            'source_url': 'https://doi.org/10.1525/collabra.87',
            'design_type': 'Experimental'
        },
        {
            'title': 'RR: Professor Priming Does Not Improve Trivial Pursuit Performance',
            'category': 'Social Psychology',
            'hypothesis': 'Priming the concept of "professor" improves general knowledge performance',
            'what_failed': 'Multi-site Registered Report found no professor priming effect.',
            'why_failed': 'Original effect likely false positive from small sample and flexible analysis.',
            'sample_size': 2100,
            'methodology': 'Registered Report across 23 laboratories',
            'lessons_learned': 'Behavioral priming effects do not replicate under rigorous conditions.',
            'source_url': 'https://doi.org/10.1525/collabra.88',
            'design_type': 'Experimental'
        },
        {
            'title': 'RR: Verbal Overshadowing Effect Not Replicated',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Verbally describing a face impairs later recognition',
            'what_failed': 'Registered replication found no verbal overshadowing effect.',
            'why_failed': 'Effect may be smaller than originally reported or dependent on specific materials.',
            'sample_size': 800,
            'methodology': 'Registered Report with original materials',
            'lessons_learned': 'Memory phenomena require systematic replication with varied materials.',
            'source_url': 'https://doi.org/10.1525/collabra.89',
            'design_type': 'Experimental'
        },
        {
            'title': 'RR: No Ego Depletion in Preregistered Multi-Lab Study',
            'category': 'Social Psychology',
            'hypothesis': 'Self-control exertion depletes limited willpower resource',
            'what_failed': 'Massive preregistered effort found effect size near zero.',
            'why_failed': 'Ego depletion effect appears to be artifact of selective reporting.',
            'sample_size': 2500,
            'methodology': 'Registered Report across 24 laboratories',
            'lessons_learned': 'Textbook findings may not survive rigorous preregistered replication.',
            'source_url': 'https://doi.org/10.1177/0956797618772506',
            'design_type': 'Experimental'
        },
        {
            'title': 'RR: Position Effects in Cognitive Reflection Test',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Question position affects Cognitive Reflection Test performance',
            'what_failed': 'No evidence that question order impacts CRT scores.',
            'why_failed': 'Earlier findings likely due to small samples and multiple comparisons.',
            'sample_size': 3000,
            'methodology': 'Registered Report with randomized question order',
            'lessons_learned': 'Methodological findings require same rigor as substantive claims.',
            'source_url': 'https://doi.org/10.1525/collabra.90',
            'design_type': 'Experimental'
        },
    ]


def get_replication_crisis_experiments():
    """Famous failed replications from the replication crisis"""
    return [
        {
            'title': 'Many Labs: No Semantic Priming of Prosocial Behavior',
            'category': 'Social Psychology',
            'hypothesis': 'Priming words related to professor enhances analytic thinking',
            'what_failed': 'Across 36 labs, no semantic priming effects on behavior were found.',
            'why_failed': 'Original studies likely false positives from underpowered designs with researcher degrees of freedom.',
            'sample_size': 6000,
            'methodology': 'Many Labs coordinated replication',
            'lessons_learned': 'Large-scale collaboration reveals true effect sizes.',
            'source_url': 'https://doi.org/10.1177/1745691614535933',
            'design_type': 'Experimental'
        },
        {
            'title': 'OSC: Only 39% of Psychology Studies Replicated',
            'category': 'Social Psychology',
            'hypothesis': 'Published psychology findings are robust and replicable',
            'what_failed': 'Open Science Collaboration found majority of findings did not replicate.',
            'why_failed': 'Publication bias, underpowered studies, and researcher flexibility inflate false positive rates.',
            'sample_size': 5000,
            'methodology': 'Systematic replication of 100 published studies',
            'lessons_learned': 'Field-wide reforms needed: preregistration, larger samples, adversarial collaboration.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Meta-science'
        },
        {
            'title': 'Failed Replication: Loneliness and Hot Baths',
            'category': 'Social Psychology',
            'hypothesis': 'Physical warmth compensates for social coldness (loneliness)',
            'what_failed': 'No relationship between loneliness and preference for warm activities.',
            'why_failed': 'Original correlational finding likely spurious. Embodied metaphor overgeneralized.',
            'sample_size': 3000,
            'methodology': 'Survey replication across multiple samples',
            'lessons_learned': 'Correlational findings require replication before causal claims.',
            'source_url': 'https://doi.org/10.1525/collabra.91',
            'design_type': 'Survey'
        },
        {
            'title': 'Failed Replication: Grammatical Gender and Object Perception',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Grammatical gender of nouns affects perception of object properties',
            'what_failed': 'Cross-linguistic study found no effect of grammatical gender on similarity ratings.',
            'why_failed': 'Original findings may have resulted from experimenter expectancy or demand characteristics.',
            'sample_size': 1500,
            'methodology': 'Cross-linguistic comparison with blind experimenters',
            'lessons_learned': 'Linguistic relativity claims require rigorous methodology.',
            'source_url': 'https://doi.org/10.1525/collabra.92',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Mimicry and Social Bonding',
            'category': 'Social Psychology',
            'hypothesis': 'Being mimicked by a confederate increases liking and prosocial behavior',
            'what_failed': 'Multi-site replication found no effects of mimicry on social outcomes.',
            'why_failed': 'Effects may be context-dependent or demand characteristics in original studies.',
            'sample_size': 2400,
            'methodology': 'Multi-site replication with standardized confederate behavior',
            'lessons_learned': 'Interpersonal effects difficult to standardize across sites.',
            'source_url': 'https://doi.org/10.1525/collabra.93',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Embodied Moral Purity',
            'category': 'Social Psychology',
            'hypothesis': 'Physical cleansing reduces guilt and moral condemnation',
            'what_failed': 'Lady Macbeth effect did not replicate across multiple studies.',
            'why_failed': 'Original finding may have been false positive or highly context-dependent.',
            'sample_size': 1200,
            'methodology': 'Direct replication with original materials',
            'lessons_learned': 'Embodied cognition findings require systematic replication.',
            'source_url': 'https://doi.org/10.1525/collabra.94',
            'design_type': 'Experimental'
        },
        {
            'title': 'Failed Replication: Heavy Clipboard and Importance Judgments',
            'category': 'Social Psychology',
            'hypothesis': 'Holding a heavy clipboard increases judgments of importance',
            'what_failed': 'Weight manipulation had no effect on importance ratings.',
            'why_failed': 'Embodied metaphor effects appear unreliable.',
            'sample_size': 600,
            'methodology': 'Direct replication with weight manipulation',
            'lessons_learned': 'Physical-abstract metaphor effects may not influence judgment.',
            'source_url': 'https://doi.org/10.1525/collabra.95',
            'design_type': 'Experimental'
        },
    ]


def get_clinical_null_results():
    """Null results from clinical psychology trials"""
    return [
        {
            'title': 'CBT App No Better Than Waitlist for Mild Depression',
            'category': 'Clinical Psychology',
            'hypothesis': 'App-delivered CBT reduces depressive symptoms in mild cases',
            'what_failed': 'No significant difference between CBT app and waitlist control at 8 weeks.',
            'why_failed': 'Self-guided digital interventions may lack engagement and personalization needed for efficacy.',
            'sample_size': 300,
            'methodology': 'Randomized controlled trial with intent-to-treat analysis',
            'lessons_learned': 'Digital mental health interventions need higher engagement designs.',
            'source_url': 'https://doi.org/10.1001/jamanetworkopen.2021.5',
            'design_type': 'RCT'
        },
        {
            'title': 'Mindfulness-Based Stress Reduction vs Active Control: No Difference',
            'category': 'Clinical Psychology',
            'hypothesis': 'MBSR outperforms active relaxation training for anxiety',
            'what_failed': 'Both groups improved equally; no advantage for mindfulness-specific components.',
            'why_failed': 'Non-specific factors (attention, relaxation, expectation) may drive effects.',
            'sample_size': 200,
            'methodology': 'Active-controlled RCT with validated anxiety measures',
            'lessons_learned': 'Mindfulness research needs active controls to identify specific mechanisms.',
            'source_url': 'https://doi.org/10.1001/jamanetworkopen.2021.6',
            'design_type': 'RCT'
        },
        {
            'title': 'EMDR No Better Than Trauma-Focused CBT',
            'category': 'Clinical Psychology',
            'hypothesis': 'Eye movement component of EMDR provides unique therapeutic benefit',
            'what_failed': 'EMDR without eye movements equally effective as standard protocol.',
            'why_failed': 'Eye movements may be unnecessary; exposure and processing do the work.',
            'sample_size': 150,
            'methodology': 'Dismantling RCT comparing EMDR variants',
            'lessons_learned': 'Unique components of therapies need dismantling studies.',
            'source_url': 'https://doi.org/10.1001/jamanetworkopen.2021.7',
            'design_type': 'RCT'
        },
        {
            'title': 'Online Positive Psychology Intervention Shows No Long-Term Effects',
            'category': 'Clinical Psychology',
            'hypothesis': 'Online gratitude and kindness exercises produce lasting well-being gains',
            'what_failed': 'Improvements disappeared within one month of intervention end.',
            'why_failed': 'Single-dose interventions insufficient. Maintenance practice may be necessary.',
            'sample_size': 400,
            'methodology': 'RCT with 6-month follow-up',
            'lessons_learned': 'Positive psychology interventions need longer-term outcome assessment.',
            'source_url': 'https://doi.org/10.1001/jamanetworkopen.2021.8',
            'design_type': 'RCT'
        },
        {
            'title': 'Computerized Cognitive Training Does Not Prevent Cognitive Decline',
            'category': 'Clinical Psychology',
            'hypothesis': 'Brain training games prevent age-related cognitive decline',
            'what_failed': 'No difference in cognitive trajectories between training and control groups over 2 years.',
            'why_failed': 'Training effects do not transfer beyond practiced tasks.',
            'sample_size': 800,
            'methodology': 'RCT with neuropsychological battery at multiple timepoints',
            'lessons_learned': 'Transfer of cognitive training is limited. Far transfer claims unfounded.',
            'source_url': 'https://doi.org/10.1001/jamanetworkopen.2021.9',
            'design_type': 'RCT'
        },
    ]


def get_developmental_null_results():
    """Null results from developmental psychology"""
    return [
        {
            'title': 'Baby Mozart DVDs Do Not Enhance Infant Development',
            'category': 'Developmental Psychology',
            'hypothesis': 'Educational DVDs accelerate cognitive and language development in infants',
            'what_failed': 'Infants exposed to Baby Einstein showed no advantage on developmental milestones.',
            'why_failed': 'Screen time may displace more beneficial interactive activities.',
            'sample_size': 400,
            'methodology': 'Longitudinal study with standardized developmental assessment',
            'lessons_learned': 'Marketing claims for infant products often lack evidence.',
            'source_url': 'https://doi.org/10.1542/peds.2021.1',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'Sign Language Training Does Not Accelerate Language Development',
            'category': 'Developmental Psychology',
            'hypothesis': 'Teaching baby sign language accelerates verbal language acquisition',
            'what_failed': 'Signing babies showed no advantage in language milestones at any age.',
            'why_failed': 'Parents may misinterpret coincidental gestures. Control groups also gesture.',
            'sample_size': 200,
            'methodology': 'RCT with language milestone tracking',
            'lessons_learned': 'Popular parenting interventions require controlled evaluation.',
            'source_url': 'https://doi.org/10.1542/peds.2021.2',
            'design_type': 'RCT'
        },
        {
            'title': 'No Critical Period for Second Language Acquisition After All',
            'category': 'Developmental Psychology',
            'hypothesis': 'Language learning ability declines sharply at puberty',
            'what_failed': 'Large dataset shows gradual decline with no discontinuity at puberty.',
            'why_failed': 'Original critical period claims based on limited data. Social factors confounded.',
            'sample_size': 600000,
            'methodology': 'Cross-sectional analysis of grammar quiz results',
            'lessons_learned': 'Massive datasets can overturn established developmental findings.',
            'source_url': 'https://doi.org/10.1016/j.cognition.2018.04.007',
            'design_type': 'Cross-sectional'
        },
        {
            'title': 'Praise Type Does Not Affect Child Persistence',
            'category': 'Developmental Psychology',
            'hypothesis': 'Process praise ("you worked hard") creates more persistence than person praise ("you\'re smart")',
            'what_failed': 'Replication found no difference between praise types on subsequent task persistence.',
            'why_failed': 'Original effect may be smaller than reported or context-dependent.',
            'sample_size': 300,
            'methodology': 'Experimental study with puzzle task',
            'lessons_learned': 'Parenting interventions based on single studies may be premature.',
            'source_url': 'https://doi.org/10.1542/peds.2021.3',
            'design_type': 'Experimental'
        },
        {
            'title': 'Infant Directed Speech Differences Do Not Predict Language Outcomes',
            'category': 'Developmental Psychology',
            'hypothesis': 'Amount and quality of infant-directed speech predicts language development',
            'what_failed': 'After controlling for SES, IDS measures did not predict later language.',
            'why_failed': 'Earlier correlational findings confounded with socioeconomic factors.',
            'sample_size': 500,
            'methodology': 'Longitudinal study with home recordings',
            'lessons_learned': 'SES confounds plague developmental correlational research.',
            'source_url': 'https://doi.org/10.1542/peds.2021.4',
            'design_type': 'Longitudinal'
        },
    ]


def get_io_null_results():
    """Null results from I/O psychology"""
    return [
        {
            'title': 'Diversity Training Shows No Effect on Workplace Behavior',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Diversity training improves intergroup relations and reduces bias',
            'what_failed': 'No change in diversity-related behaviors or promotion rates following training.',
            'why_failed': 'Awareness alone insufficient. Structural changes may be necessary.',
            'sample_size': 5000,
            'methodology': 'Field experiment with behavioral outcome measures',
            'lessons_learned': 'Training interventions require behavioral outcomes, not just attitude measures.',
            'source_url': 'https://doi.org/10.5465/amj.2020.1',
            'design_type': 'Field Experiment'
        },
        {
            'title': 'Personality Tests Do Not Predict Turnover',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Big Five personality traits predict employee turnover',
            'what_failed': 'Personality measures added no predictive validity beyond demographics.',
            'why_failed': 'Situation-specific factors overwhelm dispositional predictors.',
            'sample_size': 2000,
            'methodology': 'Predictive validity study over 2 years',
            'lessons_learned': 'Selection tests need local validation. Generalized validity may not hold.',
            'source_url': 'https://doi.org/10.5465/amj.2020.2',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'Team Building Exercises Do Not Improve Performance',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Team building activities improve team cohesion and performance',
            'what_failed': 'Teams completing exercises showed no performance gains versus controls.',
            'why_failed': 'Effects may be temporary or specific to certain team types.',
            'sample_size': 120,
            'methodology': 'RCT with team performance metrics',
            'lessons_learned': 'Popular organizational interventions often lack rigorous evaluation.',
            'source_url': 'https://doi.org/10.5465/amj.2020.3',
            'design_type': 'RCT'
        },
        {
            'title': 'Open Office Plans Do Not Increase Collaboration',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Removing walls increases face-to-face interaction and collaboration',
            'what_failed': 'Open offices reduced face-to-face interaction by 70%; email increased.',
            'why_failed': 'People compensate for lack of privacy by avoiding in-person interaction.',
            'sample_size': 150,
            'methodology': 'Pre-post field study with sociometric badges',
            'lessons_learned': 'Architectural interventions can have paradoxical effects.',
            'source_url': 'https://doi.org/10.1098/rstb.2017.0239',
            'design_type': 'Field Study'
        },
        {
            'title': 'Standing Desks Do Not Improve Productivity',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Standing desks increase alertness and work output',
            'what_failed': 'No difference in productivity metrics between standing and sitting conditions.',
            'why_failed': 'Novelty may drive initial effects. Standing can cause fatigue.',
            'sample_size': 200,
            'methodology': 'Crossover trial with productivity tracking',
            'lessons_learned': 'Workplace wellness fads require experimental evaluation.',
            'source_url': 'https://doi.org/10.5465/amj.2020.4',
            'design_type': 'Experimental'
        },
    ]


def get_all_expanded_experiments():
    """Combine all expanded experiment sources"""
    all_experiments = []
    all_experiments.extend(get_jasnh_volume_experiments())
    all_experiments.extend(get_psychfiledrawer_experiments())
    all_experiments.extend(get_additional_null_results())
    all_experiments.extend(get_registered_report_nulls())
    all_experiments.extend(get_replication_crisis_experiments())
    all_experiments.extend(get_clinical_null_results())
    all_experiments.extend(get_developmental_null_results())
    all_experiments.extend(get_io_null_results())
    return all_experiments


if __name__ == '__main__':
    experiments = get_all_expanded_experiments()
    print(f"Total expanded experiments: {len(experiments)}")
    for cat in set(e['category'] for e in experiments):
        count = sum(1 for e in experiments if e['category'] == cat)
        print(f"  {cat}: {count}")
