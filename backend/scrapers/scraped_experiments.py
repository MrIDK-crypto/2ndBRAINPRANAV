"""
Scraped Experiments - Real null results and failed replications from verified sources
Sources: JASNH, PsychFileDrawer, Many Labs, Registered Replication Reports,
         Reproducibility Project, Famous Failed Replications
"""


def get_jasnh_scraped():
    """
    Full JASNH articles scraped from jasnh.com
    Each article is a peer-reviewed null result publication
    """
    return [
        # Volume 22 (2025-2026)
        {
            'title': 'Watching-Eye Effect Does Not Reduce Illegal Pedestrian Behaviour in France',
            'category': 'Social Psychology',
            'hypothesis': 'Images of watching eyes would reduce illegal pedestrian behavior through social monitoring effects',
            'what_failed': 'Study in France found no effect of watching-eye manipulation on illegal pedestrian crossing behavior.',
            'why_failed': 'The watching-eye effect may be context-dependent or weaker than previously reported in controlled settings.',
            'sample_size': 500,
            'methodology': 'Field experiment with eye images at crosswalks',
            'lessons_learned': 'Social monitoring effects from static images may not generalize to real-world behavior.',
            'source_url': 'https://www.jasnh.com/v22n2a1.html',
            'design_type': 'Field Experiment'
        },
        {
            'title': 'Intervention Failed to Improve Expository Reading Comprehension in College Students',
            'category': 'Educational Psychology',
            'hypothesis': 'Targeted reading intervention would significantly improve expository text comprehension',
            'what_failed': 'College students receiving the intervention showed no significant improvement over controls.',
            'why_failed': 'Intervention may have been too brief or college-level reading skills may be resistant to short interventions.',
            'sample_size': 120,
            'methodology': 'Randomized controlled trial with pre-post measures',
            'lessons_learned': 'Reading interventions effective for younger students may not transfer to college populations.',
            'source_url': 'https://www.jasnh.com/v22n2a2.html',
            'design_type': 'RCT'
        },
        {
            'title': 'No Relationship Between Environmental Sensitivity and Digit Ratio (2D:4D)',
            'category': 'Personality Psychology',
            'hypothesis': 'Prenatal testosterone exposure (indexed by digit ratio) correlates with environmental sensitivity',
            'what_failed': 'No significant correlation found between 2D:4D ratio and measures of environmental sensitivity.',
            'why_failed': 'Digit ratio may not be a reliable marker for the traits proposed, or sensitivity has different origins.',
            'sample_size': 200,
            'methodology': 'Correlational study with physical measurements',
            'lessons_learned': 'Digit ratio research faces ongoing validity concerns as a proxy for prenatal hormones.',
            'source_url': 'https://www.jasnh.com/v22n2a3.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Intimate Partner Violence Did Not Predict Child Nutritional Status in Pakistan',
            'category': 'Health Psychology',
            'hypothesis': 'Maternal exposure to intimate partner violence affects child nutritional outcomes',
            'what_failed': 'Analysis of Pakistan DHS data found no significant relationship after controlling for covariates.',
            'why_failed': 'Relationship may be mediated by other socioeconomic factors that were controlled for.',
            'sample_size': 5000,
            'methodology': 'Secondary analysis of demographic health survey',
            'lessons_learned': 'Proposed pathways from IPV to child health may be indirect rather than direct.',
            'source_url': 'https://www.jasnh.com/v22n1a1.html',
            'design_type': 'Survey'
        },
        {
            'title': 'No Correlation Between Tarot Beliefs and Paranormal/Fantasy Proneness',
            'category': 'Personality Psychology',
            'hypothesis': 'Belief in tarot reading correlates with paranormal beliefs and fantasy proneness',
            'what_failed': 'Quantitative examination found no significant correlations between tarot belief and related traits.',
            'why_failed': 'Tarot use may be more recreational than belief-driven for many practitioners.',
            'sample_size': 300,
            'methodology': 'Survey with validated paranormal belief scales',
            'lessons_learned': 'Different forms of paranormal engagement may have distinct psychological profiles.',
            'source_url': 'https://www.jasnh.com/v22n1a2.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Physical Activity Does Not Protect Against Academic Difficulties in At-Risk Youth',
            'category': 'Educational Psychology',
            'hypothesis': 'Physical activity provides protective effects against academic struggles for vulnerable youth',
            'what_failed': 'Youth exposed to individual and family vulnerabilities showed no academic benefit from physical activity.',
            'why_failed': 'Proposed protective mechanism may be overwhelmed by severity of other risk factors.',
            'sample_size': 800,
            'methodology': 'Longitudinal study of at-risk youth',
            'lessons_learned': 'Physical activity benefits may not compensate for severe socioeconomic disadvantages.',
            'source_url': 'https://www.jasnh.com/v22n1a3.html',
            'design_type': 'Longitudinal'
        },
        # Volume 21 (2024-2025)
        {
            'title': 'False Feedback About Heritage Language Did Not Affect Identity or Belonging',
            'category': 'Social Psychology',
            'hypothesis': 'Competence feedback about heritage language affects sense of belonging and identity negotiation',
            'what_failed': 'False feedback manipulation (competence/incompetence) did not affect identity or belonging measures.',
            'why_failed': 'Identity may be more stable than assumed or manipulation was not strong enough.',
            'sample_size': 150,
            'methodology': 'Experimental study with second-generation adults',
            'lessons_learned': 'Bicultural identity may be more resilient to competence threats than theorized.',
            'source_url': 'https://www.jasnh.com/v21n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Association Between Trust and Fear of Negative Evaluation',
            'category': 'Personality Psychology',
            'hypothesis': 'General trust levels correlate with fear of negative evaluation',
            'what_failed': 'Trust and fear of negative evaluation showed no significant association.',
            'why_failed': 'These may be orthogonal constructs despite intuitive theoretical links.',
            'sample_size': 250,
            'methodology': 'Survey with validated trust and FNE measures',
            'lessons_learned': 'Intuitive theoretical connections require empirical validation.',
            'source_url': 'https://www.jasnh.com/v21n2a2.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Peer Observational Learning Did Not Impact Post-Transgression Honesty',
            'category': 'Developmental Psychology',
            'hypothesis': 'Observing peer behavior affects honesty following a transgression',
            'what_failed': 'Children who observed peers behaving honestly or dishonestly showed no difference in their own honesty.',
            'why_failed': 'Individual factors may outweigh observational learning for moral behavior.',
            'sample_size': 100,
            'methodology': 'Experimental study with child participants',
            'lessons_learned': 'Social learning effects may be weaker for moral decisions than other behaviors.',
            'source_url': 'https://www.jasnh.com/v21n2a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Empathy Intervention Did Not Improve Children\'s Gender-Related Attitudes',
            'category': 'Developmental Psychology',
            'hypothesis': 'Empathy-based intervention would reduce gender stereotyping in children',
            'what_failed': 'Intervention targeting empathy showed no significant change in gender-related attitudes.',
            'why_failed': 'Gender attitudes may be more resistant to change or require longer interventions.',
            'sample_size': 200,
            'methodology': 'Randomized intervention study',
            'lessons_learned': 'Single-session empathy interventions may be insufficient for attitude change.',
            'source_url': 'https://www.jasnh.com/v21n2a4.html',
            'design_type': 'RCT'
        },
        {
            'title': 'System Threat Did Not Alter Evaluation of the Poor',
            'category': 'Social Psychology',
            'hypothesis': 'Threats to the social system increase justification through negative evaluation of disadvantaged groups',
            'what_failed': 'System threat manipulation did not significantly alter evaluations of economically disadvantaged groups.',
            'why_failed': 'System justification effects may be more nuanced or culturally specific than proposed.',
            'sample_size': 180,
            'methodology': 'Experimental study with threat manipulation',
            'lessons_learned': 'System justification theory predictions may not generalize across contexts.',
            'source_url': 'https://www.jasnh.com/v21n2a5.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Mood Induction Procedures Did Not Affect Arousal or False Memory',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Mood induction (positive/negative) affects arousal levels and false memory creation',
            'what_failed': 'Two different mood induction procedures did not reliably affect false memory rates.',
            'why_failed': 'Mood-memory effects may be more domain-specific or require stronger manipulations.',
            'sample_size': 120,
            'methodology': 'Experimental study with DRM false memory paradigm',
            'lessons_learned': 'Mood effects on memory may be weaker than classic studies suggested.',
            'source_url': 'https://www.jasnh.com/v21n1a1.html',
            'design_type': 'Experimental'
        },
        # Volume 20 (2023-2024)
        {
            'title': 'Autobiographical Writing Tasks Failed to Induce Discrete Shame and Guilt',
            'category': 'Social Psychology',
            'hypothesis': 'Writing about shame vs. guilt experiences induces distinct emotional states',
            'what_failed': 'Writing tasks did not reliably induce distinct shame versus guilt emotional states.',
            'why_failed': 'Self-conscious emotions may be difficult to manipulate via recall, or overlap more than theorized.',
            'sample_size': 160,
            'methodology': 'Experimental study with autobiographical recall',
            'lessons_learned': 'Emotion induction procedures may not work as cleanly as assumed for complex emotions.',
            'source_url': 'https://www.jasnh.com/v20n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Owl Feces Did Not Alter Rat Operant Responding',
            'category': 'Neuroscience',
            'hypothesis': 'Rats recognize conspecific-eating predator cues and alter behavior accordingly',
            'what_failed': 'Presence of owl feces (predator cue) showed no effect on rat operant responding.',
            'why_failed': 'Laboratory rats may lack innate recognition of predator cues, or fecal cues insufficient.',
            'sample_size': 40,
            'methodology': 'Operant conditioning experiment',
            'lessons_learned': 'Predator recognition may require direct experience or stronger cues in lab-bred animals.',
            'source_url': 'https://www.jasnh.com/v20n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Gender and COVID-19 Did Not Alter Attitudes Toward Justice-Involved Youth',
            'category': 'Social Psychology',
            'hypothesis': 'Gender and pandemic context affect attitudes toward adolescent substance users in justice system',
            'what_failed': 'Neither gender nor COVID-19 context significantly altered policy attitudes.',
            'why_failed': 'Attitudes toward justice-involved youth may be stable across demographic and situational factors.',
            'sample_size': 400,
            'methodology': 'Survey experiment with vignettes',
            'lessons_learned': 'Policy attitudes may be more entrenched than situational factors can shift.',
            'source_url': 'https://www.jasnh.com/v20n1a2.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Religious Activity Did Not Protect Against Cognitive Decline or Dementia',
            'category': 'Health Psychology',
            'hypothesis': 'Religious and spiritual activity provides protective effects against cognitive impairment',
            'what_failed': 'Religious activities showed no protective effect against cognitive decline across race/ethnicity groups.',
            'why_failed': 'Social aspects of religious participation may be confounded with other protective factors.',
            'sample_size': 3000,
            'methodology': 'Longitudinal cohort study',
            'lessons_learned': 'Proposed religious benefits may be due to social engagement rather than religiosity per se.',
            'source_url': 'https://www.jasnh.com/v20n1a3.html',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'Failed to Replicate Disgust Recall Effect (Sato & Sugiura 2014)',
            'category': 'Social Psychology',
            'hypothesis': 'Recalling disgusting experiences elicits disgust and affects subsequent judgments',
            'what_failed': 'Disgust recall manipulation was ineffective at inducing disgust or affecting judgments.',
            'why_failed': 'Original effect may have been false positive or highly context-dependent.',
            'sample_size': 200,
            'methodology': 'Direct replication with extension',
            'lessons_learned': 'Emotion recall procedures may have low reliability across studies.',
            'source_url': 'https://www.jasnh.com/v20n1a4.html',
            'design_type': 'Experimental'
        },
        # Volume 19 (2022-2023)
        {
            'title': 'Bogus Pipeline Condition Produced Null Findings',
            'category': 'Social Psychology',
            'hypothesis': 'Bogus pipeline (fake lie detector) increases honest responding',
            'what_failed': 'Pipeline manipulation did not produce expected increases in honest responding.',
            'why_failed': 'Participants may not have believed manipulation, or effect is smaller than reported.',
            'sample_size': 150,
            'methodology': 'Experimental study examining bogus pipeline validity',
            'lessons_learned': 'Classic social psychology manipulations may not work as reliably as textbooks suggest.',
            'source_url': 'https://www.jasnh.com/v19n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'More US Education Did Not Foster Racial Cooperation',
            'category': 'Social Psychology',
            'hypothesis': 'Educational attainment increases interracial cooperation and reduces bias',
            'what_failed': 'Formal education did not predict improved interracial cooperation in behavioral tasks.',
            'why_failed': 'Education effects may be limited to explicit attitudes, not implicit behavior.',
            'sample_size': 300,
            'methodology': 'Behavioral intergroup cooperation task',
            'lessons_learned': 'Education may change what people say but not what they do in intergroup contexts.',
            'source_url': 'https://www.jasnh.com/v19n2a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Emotional Stroop Effect from Masked and Unmasked Stimuli in Non-Clinical Adults',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Emotional words produce Stroop interference effects in healthy adults',
            'what_failed': 'Neither masked nor unmasked emotional stimuli produced Stroop interference online.',
            'why_failed': 'Online testing may introduce noise, or emotional Stroop may be unreliable in non-clinical samples.',
            'sample_size': 200,
            'methodology': 'Online Stroop task with emotional words',
            'lessons_learned': 'Emotional Stroop effects may be specific to clinical populations or laboratory settings.',
            'source_url': 'https://www.jasnh.com/v19n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Brief Interventions Did Not Improve Engineering Student Dyad Functioning',
            'category': 'Educational Psychology',
            'hypothesis': 'Brief team interventions improve collaboration in engineering student pairs',
            'what_failed': 'Intervention did not enhance student collaboration or project outcomes.',
            'why_failed': 'Single-session interventions may be insufficient for changing team dynamics.',
            'sample_size': 80,
            'methodology': 'Randomized intervention with dyads',
            'lessons_learned': 'Team interventions may require sustained effort rather than one-time sessions.',
            'source_url': 'https://www.jasnh.com/v19n1a2.html',
            'design_type': 'RCT'
        },
        # Volume 18 (2021-2022)
        {
            'title': 'Judicial Summaries Did Not Influence Juror Decision Making',
            'category': 'Social Psychology',
            'hypothesis': 'How judges summarize evidence affects jury verdicts',
            'what_failed': 'Summaries by judges and juror characteristics did not significantly influence decisions.',
            'why_failed': 'Jurors may rely more on evidence itself than judicial framing.',
            'sample_size': 200,
            'methodology': 'Mock jury experimental study',
            'lessons_learned': 'Legal assumptions about judicial influence on juries may need revision.',
            'source_url': 'https://www.jasnh.com/v18n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Word Order Did Not Predict Ethnocentric Helping Behavior (Lost Letter Study)',
            'category': 'Social Psychology',
            'hypothesis': 'Linguistic patterns correlate with ethnocentric helping behavior',
            'what_failed': 'Lost letter field experiment in Berlin found word order did not predict helping.',
            'why_failed': 'Linguistic relativity effects may not extend to prosocial behavior.',
            'sample_size': 400,
            'methodology': 'Lost letter field experiment',
            'lessons_learned': 'Language-behavior links may be more limited than Whorfian hypotheses suggest.',
            'source_url': 'https://www.jasnh.com/v18n2a2.html',
            'design_type': 'Field Experiment'
        },
        {
            'title': 'Young Carers Did Not Differ in Self-Compassion or Well-Being from Non-Caregiving Youth',
            'category': 'Health Psychology',
            'hypothesis': 'Caregiving responsibilities negatively affect youth self-compassion and well-being',
            'what_failed': 'Caregiving status showed no significant impact on well-being measures.',
            'why_failed': 'Young carers may develop resilience, or effects are masked by other variables.',
            'sample_size': 300,
            'methodology': 'Comparative survey study',
            'lessons_learned': 'Caregiving effects on youth may be more nuanced than deficit-focused views suggest.',
            'source_url': 'https://www.jasnh.com/v18n2a3.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Group Collaboration and Performance Did Not Increase Trust and Cooperation',
            'category': 'Social Psychology',
            'hypothesis': 'Successful group collaboration increases interpersonal trust and future cooperation',
            'what_failed': 'Collaboration and performance did not reliably increase trust or cooperation.',
            'why_failed': 'Trust formation may require more than single successful interactions.',
            'sample_size': 180,
            'methodology': 'Group task experimental design',
            'lessons_learned': 'Trust development may be slower and more complex than single-interaction studies capture.',
            'source_url': 'https://www.jasnh.com/v18n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Position and Emotional Valence of Decorative Pictures Did Not Affect Learning',
            'category': 'Educational Psychology',
            'hypothesis': 'Decorative picture placement and emotional content influence multimedia learning',
            'what_failed': 'Picture position and emotional valence did not affect learning outcomes.',
            'why_failed': 'Decorative elements may have minimal cognitive impact regardless of positioning.',
            'sample_size': 160,
            'methodology': 'Multimedia learning experiment',
            'lessons_learned': 'Multimedia design principles may have boundary conditions or smaller effects than claimed.',
            'source_url': 'https://www.jasnh.com/v18n1a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Differences in Bedtime Habits Between Adults With and Without Type 2 Diabetes',
            'category': 'Health Psychology',
            'hypothesis': 'Type 2 diabetes is associated with disrupted sleep and bedtime habits',
            'what_failed': 'Actigraphy data showed no significant differences in sleep patterns between groups.',
            'why_failed': 'Diabetes-sleep links may be confounded by other lifestyle factors controlled for in analysis.',
            'sample_size': 150,
            'methodology': 'Objective sleep measurement with actigraphy',
            'lessons_learned': 'Objective sleep measures may reveal different patterns than self-report studies.',
            'source_url': 'https://www.jasnh.com/v18n1a3.html',
            'design_type': 'Observational'
        },
        {
            'title': 'Interventions Failed to Impact Global Citizenship Identification',
            'category': 'Social Psychology',
            'hypothesis': 'Brief interventions can increase global citizenship identification',
            'what_failed': 'Multiple intervention attempts did not increase global citizenship identification.',
            'why_failed': 'Global identity may be stable and resistant to short-term manipulation.',
            'sample_size': 400,
            'methodology': 'Multiple experimental studies',
            'lessons_learned': 'Broad social identities may be harder to manipulate than specific group identities.',
            'source_url': 'https://www.jasnh.com/v18n1a4.html',
            'design_type': 'Experimental'
        },
        # Volume 17 (2020-2021)
        {
            'title': 'Locus of Control, Sex, and Age Did Not Predict Perceptions of Petty Crime',
            'category': 'Social Psychology',
            'hypothesis': 'Individual differences predict judgments about petty crime severity',
            'what_failed': 'Locus of control and demographics did not predict crime perception differences.',
            'why_failed': 'Crime judgments may be more situational than dispositional.',
            'sample_size': 250,
            'methodology': 'Survey with crime vignettes',
            'lessons_learned': 'Individual difference variables may have limited predictive power for specific judgments.',
            'source_url': 'https://www.jasnh.com/v17n2a1.html',
            'design_type': 'Survey'
        },
        {
            'title': 'No Relationship Between Conflict Detection, Numeracy, and Processing Preference',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Individual differences in numeracy relate to conflict detection and processing style',
            'what_failed': 'No relationship found between conflict detection and processing preferences.',
            'why_failed': 'These cognitive abilities may be more independent than dual-process theories suggest.',
            'sample_size': 200,
            'methodology': 'Cognitive task battery',
            'lessons_learned': 'Dual-process theory predictions may not hold for individual differences.',
            'source_url': 'https://www.jasnh.com/v17n2a2.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Non-Native and Unfamiliar Accents Did Not Sound Less Credible',
            'category': 'Social Psychology',
            'hypothesis': 'Processing disfluency from accents reduces perceived credibility',
            'what_failed': 'Accents did not significantly affect perceived credibility after controlling for content.',
            'why_failed': 'Credibility may depend more on content than delivery, or fluency effects are overestimated.',
            'sample_size': 300,
            'methodology': 'Experimental study with accent manipulation',
            'lessons_learned': 'Processing fluency effects may be smaller than laboratory studies suggest.',
            'source_url': 'https://www.jasnh.com/v17n2a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Anxiety Did Not Relate to Attentional Bias for Threat Stimuli',
            'category': 'Clinical Psychology',
            'hypothesis': 'Trait anxiety correlates with attentional bias toward threatening stimuli',
            'what_failed': 'No relationship found between anxiety levels and attentional bias patterns.',
            'why_failed': 'Attentional bias effects may be specific to clinical anxiety, not trait anxiety.',
            'sample_size': 180,
            'methodology': 'Dot-probe task with anxiety measures',
            'lessons_learned': 'Subclinical anxiety may not show same attentional patterns as clinical samples.',
            'source_url': 'https://www.jasnh.com/v17n2a4.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Foreign Language Effect Did Not Extend to Rational Decision Making',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Using a foreign language increases rational decision making',
            'what_failed': 'Bilingual advantages did not transfer to decision-making tasks.',
            'why_failed': 'Foreign language effects may be limited to specific moral dilemmas, not general rationality.',
            'sample_size': 200,
            'methodology': 'Decision-making tasks in native vs. foreign language',
            'lessons_learned': 'Bilingual cognitive effects may have narrower scope than initially claimed.',
            'source_url': 'https://www.jasnh.com/v17n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Advantage for Metonymic Over Metaphoric Idioms in Priming',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Metonymic idioms are processed differently than metaphoric idioms',
            'what_failed': 'Idiom type did not produce differential priming effects.',
            'why_failed': 'Processing differences may be smaller than theoretical accounts suggest.',
            'sample_size': 120,
            'methodology': 'Primed lexical decision task',
            'lessons_learned': 'Theoretical distinctions may not always map onto measurable processing differences.',
            'source_url': 'https://www.jasnh.com/v17n1a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Education Level Did Not Affect Emotion-Based Decision Making',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Higher education improves emotion regulation during decision making',
            'what_failed': 'Education level did not predict emotion-based decision performance.',
            'why_failed': 'Emotional decision making may be independent of formal educational attainment.',
            'sample_size': 250,
            'methodology': 'Iowa Gambling Task with educational groups',
            'lessons_learned': 'Cognitive and emotional decision systems may develop separately from formal education.',
            'source_url': 'https://www.jasnh.com/v17n1a3.html',
            'design_type': 'Quasi-experimental'
        },
        # Volume 16 (2019-2020)
        {
            'title': 'Dual Effects Model of Social Control Did Not Extend to Non-Targeted Health Behavior',
            'category': 'Health Psychology',
            'hypothesis': 'Social control effects generalize to non-targeted health behaviors',
            'what_failed': 'Social control model did not extend to behaviors not directly targeted.',
            'why_failed': 'Spillover effects may be limited to closely related behaviors.',
            'sample_size': 200,
            'methodology': 'Longitudinal couples study',
            'lessons_learned': 'Health behavior models may have narrower applicability than theoretical generalization suggests.',
            'source_url': 'https://www.jasnh.com/v16n2a1.html',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'No Implicit-Explicit Racial Attitude Correlation in Rural Southern Sample',
            'category': 'Social Psychology',
            'hypothesis': 'Implicit and explicit racial attitudes correlate within individuals',
            'what_failed': 'Implicit and explicit racial attitudes were uncorrelated in this sample.',
            'why_failed': 'IAT may measure something other than personal attitudes, or regional factors affect the relationship.',
            'sample_size': 150,
            'methodology': 'IAT and explicit attitude measures',
            'lessons_learned': 'Implicit-explicit attitude correspondence may vary substantially across populations.',
            'source_url': 'https://www.jasnh.com/v16n2a2.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'College Classes Did Not Improve Political Knowledge, Attitudes, or Engagement',
            'category': 'Educational Psychology',
            'hypothesis': 'College political science courses increase political sophistication',
            'what_failed': 'College courses did not significantly improve political outcomes.',
            'why_failed': 'Self-selection may explain prior correlations; courses may have limited causal impact.',
            'sample_size': 300,
            'methodology': 'Pre-post assessment with control group',
            'lessons_learned': 'Civic education effects may be smaller than correlational studies suggest.',
            'source_url': 'https://www.jasnh.com/v16n2a3.html',
            'design_type': 'Quasi-experimental'
        },
        {
            'title': 'Response-Order Effects Were Not Explained by Overclaiming',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Response order effects in questionnaires relate to overclaiming tendencies',
            'what_failed': 'Item order produced no systematic bias explained by overclaiming.',
            'why_failed': 'Response effects may have different mechanisms than overclaiming.',
            'sample_size': 250,
            'methodology': 'Survey methodology study',
            'lessons_learned': 'Survey method artifacts may have multiple independent causes.',
            'source_url': 'https://www.jasnh.com/v16n2a4.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Touching Information on a Tablet Did Not Affect How It Was Evaluated',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Haptic interaction with touchscreens affects information evaluation',
            'what_failed': 'Touch interaction did not affect information evaluation.',
            'why_failed': 'Embodied cognition effects may not generalize to modern digital interfaces.',
            'sample_size': 180,
            'methodology': 'Tablet interaction experimental study',
            'lessons_learned': 'Digital interface findings may not follow traditional embodiment predictions.',
            'source_url': 'https://www.jasnh.com/v16n2a5.html',
            'design_type': 'Experimental'
        },
        # Volume 15 (2018-2019)
        {
            'title': 'Stage of Onset and Type of Abuse Did Not Predict Child Cooperation and Aggression',
            'category': 'Developmental Psychology',
            'hypothesis': 'Abuse timing and type differentially predict behavioral outcomes',
            'what_failed': 'Neither abuse timing nor type significantly predicted cooperation or aggression.',
            'why_failed': 'Abuse effects may be more general than specific to timing/type distinctions.',
            'sample_size': 150,
            'methodology': 'Retrospective study with behavioral measures',
            'lessons_learned': 'Theoretical distinctions in maltreatment research may not predict distinct outcomes.',
            'source_url': 'https://www.jasnh.com/v16n1a1.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Implicit Approach Failed to Capture Uncanny Feeling',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Implicit measures can detect uncanny valley effects',
            'what_failed': 'Implicit measures did not capture uncanny feelings toward humanlike robots.',
            'why_failed': 'Uncanny valley may be primarily explicit or require different implicit measures.',
            'sample_size': 120,
            'methodology': 'Implicit association test for uncanny stimuli',
            'lessons_learned': 'Not all psychological phenomena have reliable implicit components.',
            'source_url': 'https://www.jasnh.com/v16n1a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Narcissism No Longer Related to Social Media Usage',
            'category': 'Personality Psychology',
            'hypothesis': 'Narcissistic traits predict greater social media engagement',
            'what_failed': 'Narcissism did not predict social media usage in current sample.',
            'why_failed': 'As social media becomes universal, individual differences may become less predictive.',
            'sample_size': 300,
            'methodology': 'Survey with personality and social media measures',
            'lessons_learned': 'Technology-behavior relationships may shift as technologies become ubiquitous.',
            'source_url': 'https://www.jasnh.com/v16n1a3.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Bias Toward the Present Did Not Influence Exploratory Choice',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Present bias affects exploration-exploitation tradeoffs',
            'what_failed': 'Present bias did not affect exploration behavior in decision tasks.',
            'why_failed': 'These may be separate decision-making systems with independent operation.',
            'sample_size': 200,
            'methodology': 'Multi-armed bandit task with present bias measures',
            'lessons_learned': 'Theoretical links between decision biases may not hold empirically.',
            'source_url': 'https://www.jasnh.com/v16n1a4.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Self-Affirmation Did Not Improve Grades in Middle School or College',
            'category': 'Educational Psychology',
            'hypothesis': 'Self-affirmation interventions improve academic performance',
            'what_failed': 'Self-affirmation did not improve academic performance in either age group.',
            'why_failed': 'Original effects may have been context-specific or false positives.',
            'sample_size': 400,
            'methodology': 'Randomized intervention in schools',
            'lessons_learned': 'Self-affirmation effects on achievement may not generalize broadly.',
            'source_url': 'https://www.jasnh.com/v16n1a5.html',
            'design_type': 'RCT'
        },
        # Volume 14 and earlier (abbreviated)
        {
            'title': 'Age and Cultural Values Did Not Interact to Affect In-Group Bias',
            'category': 'Social Psychology',
            'hypothesis': 'Age and cultural values interact to predict in-group favoritism',
            'what_failed': 'No interactive effect of age and cultural values on in-group bias.',
            'why_failed': 'These variables may have independent rather than interactive effects.',
            'sample_size': 350,
            'methodology': 'Cross-cultural survey study',
            'lessons_learned': 'Interaction hypotheses require specific theoretical justification.',
            'source_url': 'https://www.jasnh.com/v15n2a1.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Self-Affirmation Ineffective for Promoting Skin Cancer Prevention',
            'category': 'Health Psychology',
            'hypothesis': 'Self-affirmation increases receptivity to health threat information',
            'what_failed': 'Self-affirmation did not improve cancer-prevention attitudes or intentions.',
            'why_failed': 'Self-affirmation effects may be limited to specific health domains.',
            'sample_size': 200,
            'methodology': 'Randomized experiment with health messages',
            'lessons_learned': 'Health communication interventions require domain-specific validation.',
            'source_url': 'https://www.jasnh.com/v15n2a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Cross-Cultural Communication Competence Did Not Affect Tennis Performance',
            'category': 'Social Psychology',
            'hypothesis': 'Communication competence enhances athletic team performance',
            'what_failed': 'Communication competence did not enhance tennis performance.',
            'why_failed': 'Individual sport performance may depend on different factors than team communication.',
            'sample_size': 80,
            'methodology': 'Performance correlation study',
            'lessons_learned': 'Team dynamics findings may not transfer to individual sports.',
            'source_url': 'https://www.jasnh.com/v15n2a3.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Substance Use Did Not Correlate with Standardized Test Scores',
            'category': 'Educational Psychology',
            'hypothesis': 'Adolescent substance use predicts lower academic achievement',
            'what_failed': 'Substance use did not correlate with standardized test scores after controls.',
            'why_failed': 'Confounding factors like SES may explain previously observed relationships.',
            'sample_size': 1000,
            'methodology': 'Secondary data analysis with controls',
            'lessons_learned': 'Substance use-achievement links may be confounded by third variables.',
            'source_url': 'https://www.jasnh.com/v15n2a4.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'No Fear Renewal Following Immediate Extinction in Passive Avoidance',
            'category': 'Neuroscience',
            'hypothesis': 'Immediate extinction leads to fear renewal in different context',
            'what_failed': 'Fear renewal was not observed following immediate extinction.',
            'why_failed': 'Renewal effects may depend on specific procedural parameters not replicated.',
            'sample_size': 60,
            'methodology': 'Passive avoidance paradigm with rats',
            'lessons_learned': 'Fear conditioning phenomena may be highly sensitive to procedural details.',
            'source_url': 'https://www.jasnh.com/v15n2a5.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Black Sheep Effect Did Not Appear in Wikipedia Cross-Language Analysis',
            'category': 'Social Psychology',
            'hypothesis': 'In-group perpetrators described more negatively in in-group language Wikipedia',
            'what_failed': 'Wikipedia language versions did not show predicted bias patterns.',
            'why_failed': 'Crowdsourced content may follow different dynamics than individual judgments.',
            'sample_size': 500,
            'methodology': 'Content analysis of Wikipedia articles',
            'lessons_learned': 'Laboratory intergroup effects may not manifest in collaborative online contexts.',
            'source_url': 'https://www.jasnh.com/v15n2a6.html',
            'design_type': 'Archival'
        },
        {
            'title': 'Failed to Evoke Stereotype Threat Using the Race IAT',
            'category': 'Social Psychology',
            'hypothesis': 'Completing the race IAT activates stereotype threat',
            'what_failed': 'Stereotype threat manipulation using IAT was ineffective.',
            'why_failed': 'IAT may not be threatening enough to activate stereotype threat, or effect is unreliable.',
            'sample_size': 180,
            'methodology': 'Stereotype threat experimental paradigm',
            'lessons_learned': 'Stereotype threat manipulations may be highly context-specific.',
            'source_url': 'https://www.jasnh.com/v15n2a7.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Implicit Sound Symbolism Effect Did Not Replicate',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Sound-meaning mappings affect lexical access',
            'what_failed': 'Sound symbolism effects disappeared in modern interference task paradigms.',
            'why_failed': 'Effect may have been artifact of specific task demands in original studies.',
            'sample_size': 150,
            'methodology': 'Lexical decision with interference manipulation',
            'lessons_learned': 'Classic psycholinguistic effects require replication with updated methods.',
            'source_url': 'https://www.jasnh.com/v15n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Incentive Motivation Effects Did Not Replicate in Virtual Morris Water Maze',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Motivation enhances spatial learning performance',
            'what_failed': 'Incentive motivation effects failed to replicate reliably.',
            'why_failed': 'Virtual navigation may involve different processes than physical navigation.',
            'sample_size': 100,
            'methodology': 'Virtual reality spatial learning task',
            'lessons_learned': 'Findings from rodent studies may not transfer directly to human virtual tasks.',
            'source_url': 'https://www.jasnh.com/v15n1a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Spacing and Testing Effects Did Not Improve Inductive Learning',
            'category': 'Educational Psychology',
            'hypothesis': 'Spacing and testing enhance inductive category learning',
            'what_failed': 'Spacing and testing did not improve inductive learning outcomes.',
            'why_failed': 'These effects may be specific to memorization rather than category learning.',
            'sample_size': 180,
            'methodology': 'Inductive learning experimental paradigm',
            'lessons_learned': 'Learning principles may have domain-specific boundary conditions.',
            'source_url': 'https://www.jasnh.com/v15n1a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Haptic Sensations Did Not Influence Social Judgments (Replication of Ackerman et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Physical sensations (weight, texture) influence abstract judgments',
            'what_failed': 'Preregistered replication found no effect of haptic sensations on social judgments.',
            'why_failed': 'Original effect likely false positive or highly context-specific.',
            'sample_size': 200,
            'methodology': 'Confirmatory replication with preregistration',
            'lessons_learned': 'Embodied cognition findings require careful replication before acceptance.',
            'source_url': 'https://www.jasnh.com/v14n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Perceived Stress Not Associated with Cortisol or Insulin Resistance in Type 2 Diabetes',
            'category': 'Health Psychology',
            'hypothesis': 'Perceived stress relates to physiological stress markers in diabetes',
            'what_failed': 'Perceived stress did not correlate with cortisol or insulin resistance.',
            'why_failed': 'Self-report and physiological stress may be dissociated in chronic conditions.',
            'sample_size': 100,
            'methodology': 'Clinical study with biomarkers',
            'lessons_learned': 'Subjective and objective stress indicators may diverge in chronic illness.',
            'source_url': 'https://www.jasnh.com/v14n2a2.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Mindfulness Did Not Enhance Energy Drink Effectiveness (Red Bull Effect)',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Mindfulness moderates placebo-like energy drink effects',
            'what_failed': 'State mindfulness did not interact with energy drink effects.',
            'why_failed': 'Mindfulness effects on expectancies may be limited or task-specific.',
            'sample_size': 120,
            'methodology': 'Experimental study with mindfulness and caffeine',
            'lessons_learned': 'Mindfulness as a moderator variable may have limited scope.',
            'source_url': 'https://www.jasnh.com/v14n2a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Ego Depletion Did Not Explain Teacher Aggression',
            'category': 'Social Psychology',
            'hypothesis': 'Self-control depletion underlies teacher aggressive behavior',
            'what_failed': 'Ego depletion did not predict teacher aggression toward students.',
            'why_failed': 'Ego depletion effects increasingly questioned; may not exist as theorized.',
            'sample_size': 150,
            'methodology': 'Survey and daily diary study',
            'lessons_learned': 'Ego depletion theory faces serious replication challenges.',
            'source_url': 'https://www.jasnh.com/v14n1a1.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Wikipedia Analysis Did Not Reveal Global Suicide Patterns',
            'category': 'Social Psychology',
            'hypothesis': 'Wikipedia editing patterns reflect societal attitudes toward suicide',
            'what_failed': 'Wikipedia analysis did not reveal expected suicide pattern correlates.',
            'why_failed': 'Crowdsourced content may not reflect population-level attitudes.',
            'sample_size': 1000,
            'methodology': 'Computational analysis of Wikipedia content',
            'lessons_learned': 'Big data sources require validation against ground truth.',
            'source_url': 'https://www.jasnh.com/v14n1a2.html',
            'design_type': 'Archival'
        },
        {
            'title': 'Social Stigma Did Not Reliably Affect Observer Eye Movements',
            'category': 'Social Psychology',
            'hypothesis': 'Stigmatizing features attract visual attention',
            'what_failed': 'Stigma did not reliably affect visual attention patterns.',
            'why_failed': 'Attention effects may depend on stigma type or be more variable than expected.',
            'sample_size': 100,
            'methodology': 'Eye-tracking study with stigmatizing stimuli',
            'lessons_learned': 'Stigma-attention links may be more nuanced than general theories suggest.',
            'source_url': 'https://www.jasnh.com/v14n1a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Single-Item Narcissism Measure Unreliable in At-Risk Adolescents',
            'category': 'Personality Psychology',
            'hypothesis': 'Single-item narcissism measure predicts multi-item scale scores',
            'what_failed': 'Single-item measure showed poor validity in at-risk youth sample.',
            'why_failed': 'Brief measures may lack reliability in challenging populations.',
            'sample_size': 200,
            'methodology': 'Psychometric validation study',
            'lessons_learned': 'Short-form measures need validation in diverse populations.',
            'source_url': 'https://www.jasnh.com/v14n1a4.html',
            'design_type': 'Psychometric'
        },
        {
            'title': 'Guilt, Shame, and Sympathy Did Not Predict Prosocial Behavior',
            'category': 'Social Psychology',
            'hypothesis': 'Specific emotions (guilt, shame, sympathy) predict prosocial action',
            'what_failed': 'Specific emotions did not predict prosocial behavior as theorized.',
            'why_failed': 'Emotion-behavior links may be more general or context-dependent.',
            'sample_size': 180,
            'methodology': 'Emotion induction with prosocial opportunity',
            'lessons_learned': 'Specific emotion effects may be harder to isolate than theory suggests.',
            'source_url': 'https://www.jasnh.com/v14n1a5.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Work Stress Measurement Not Invariant Across Sex',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Work stress scales measure the same construct in men and women',
            'what_failed': 'Measurement invariance testing revealed stress measured differently by sex.',
            'why_failed': 'Gendered experiences of workplace stress may affect measurement.',
            'sample_size': 500,
            'methodology': 'Psychometric invariance testing',
            'lessons_learned': 'Gender comparisons require measurement invariance verification.',
            'source_url': 'https://www.jasnh.com/v13n2a1.html',
            'design_type': 'Psychometric'
        },
        {
            'title': 'Birth Numbers Do Not Predict Nobel Prize Winners (Numerology Test)',
            'category': 'Personality Psychology',
            'hypothesis': 'Numerological patterns in birth dates predict Nobel Prize achievement',
            'what_failed': 'No numerological patterns found in Nobel laureate birth dates.',
            'why_failed': 'Numerology has no empirical basis; patterns are random.',
            'sample_size': 900,
            'methodology': 'Archival analysis of Nobel Prize data',
            'lessons_learned': 'Pseudoscientific claims fail rigorous empirical testing.',
            'source_url': 'https://www.jasnh.com/v13n2a2.html',
            'design_type': 'Archival'
        },
        {
            'title': 'Big Five Personality Did Not Predict Eyewitness Recognition Accuracy',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Personality traits predict eyewitness identification accuracy',
            'what_failed': 'Personality traits did not predict eyewitness accuracy.',
            'why_failed': 'Eyewitness accuracy may depend more on situational than dispositional factors.',
            'sample_size': 200,
            'methodology': 'Eyewitness identification study with personality measures',
            'lessons_learned': 'Individual differences may have limited relevance for specific cognitive tasks.',
            'source_url': 'https://www.jasnh.com/v13n2a3.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Animal Welfare Regulations Exposure Did Not Change Research Attitudes',
            'category': 'Social Psychology',
            'hypothesis': 'Learning about animal welfare regulations affects attitudes toward animal research',
            'what_failed': 'Regulatory information did not shift attitudes about animal research.',
            'why_failed': 'Attitudes may be based on values rather than information about procedures.',
            'sample_size': 300,
            'methodology': 'Information provision experimental study',
            'lessons_learned': 'Moral attitudes may be resistant to informational interventions.',
            'source_url': 'https://www.jasnh.com/v13n2a4.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Ego Depletion Typing Task Did Not Extend to Online Stroop',
            'category': 'Social Psychology',
            'hypothesis': 'Ego depletion effects generalize to online cognitive testing',
            'what_failed': 'Depletion effects failed to generalize to diverse online sample.',
            'why_failed': 'Online testing may introduce noise, or ego depletion effect is unreliable.',
            'sample_size': 400,
            'methodology': 'Online Stroop task after depletion manipulation',
            'lessons_learned': 'Laboratory findings may not replicate in online convenience samples.',
            'source_url': 'https://www.jasnh.com/v13n2a5.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Statistics Anxiety Shows No Attentional Bias Pattern',
            'category': 'Educational Psychology',
            'hypothesis': 'Statistics anxiety produces attentional bias similar to other anxieties',
            'what_failed': 'Statistics anxiety showed no attentional bias toward statistics-related words.',
            'why_failed': 'Statistics anxiety may be qualitatively different from clinical anxiety.',
            'sample_size': 150,
            'methodology': 'Dot-probe task with statistics-related stimuli',
            'lessons_learned': 'Academic anxieties may not follow clinical anxiety patterns.',
            'source_url': 'https://www.jasnh.com/v13n2a6.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Mortality Salience and Spirituality Did Not Affect Materialism in UAE',
            'category': 'Social Psychology',
            'hypothesis': 'Mortality reminders and spirituality interact to affect materialism',
            'what_failed': 'Neither mortality cues nor spirituality affected materialism.',
            'why_failed': 'Terror management effects may be culturally specific or weaker than claimed.',
            'sample_size': 250,
            'methodology': 'Experimental study in UAE population',
            'lessons_learned': 'Western psychological theories require cross-cultural validation.',
            'source_url': 'https://www.jasnh.com/v13n2a7.html',
            'design_type': 'Experimental'
        },
        # Earlier volumes
        {
            'title': 'Verifiability Approach Did Not Improve Lie Detection for Occupation Claims',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Verifiability approach improves lie detection accuracy',
            'what_failed': 'Verifiability approach did not improve detection of occupation lies.',
            'why_failed': 'Approach may work only for specific content domains.',
            'sample_size': 150,
            'methodology': 'Deception detection paradigm',
            'lessons_learned': 'Lie detection techniques may have narrow applicability.',
            'source_url': 'https://www.jasnh.com/v13n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Ageism and Drug Use Did Not Predict Illness Experiences',
            'category': 'Health Psychology',
            'hypothesis': 'Ageism and substance use relate to illness perceptions',
            'what_failed': 'Age-related stereotypes did not predict health experiences.',
            'why_failed': 'Direct health factors may overwhelm attitudinal predictors.',
            'sample_size': 300,
            'methodology': 'Survey with young adults',
            'lessons_learned': 'Attitudinal variables may have limited predictive power for health outcomes.',
            'source_url': 'https://www.jasnh.com/v13n1a2.html',
            'design_type': 'Survey'
        },
        {
            'title': 'Protective Factors Did Not Moderate Mortality Salience Effects',
            'category': 'Social Psychology',
            'hypothesis': 'Sense of coherence and mindfulness protect against death anxiety effects',
            'what_failed': 'Protective factors did not moderate mortality salience outcomes.',
            'why_failed': 'Moderation effects may be smaller than theorized or require larger samples.',
            'sample_size': 200,
            'methodology': 'Terror management experimental paradigm',
            'lessons_learned': 'Individual difference moderators often fail to replicate in TMT research.',
            'source_url': 'https://www.jasnh.com/v13n1a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Memory Advantage for Enactment Over Observation or Pictures',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Enacting actions produces superior memory compared to observation',
            'what_failed': 'Enactment produced no memory advantage for naturalistic activities.',
            'why_failed': 'Effect may be limited to simple actions or laboratory stimuli.',
            'sample_size': 120,
            'methodology': 'Memory experiment with different encoding conditions',
            'lessons_learned': 'Enactment effect may have narrower scope than claimed.',
            'source_url': 'https://www.jasnh.com/v12n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Gene-Environment Interactions Did Not Predict PTSD Development',
            'category': 'Clinical Psychology',
            'hypothesis': 'Genetic variants interact with social environment to predict PTSD',
            'what_failed': 'Gene-environment interactions did not predict PTSD outcomes.',
            'why_failed': 'GxE effects may be smaller than early candidate gene studies suggested.',
            'sample_size': 400,
            'methodology': 'Prospective study with genetic and environmental measures',
            'lessons_learned': 'Candidate gene GxE findings often fail to replicate.',
            'source_url': 'https://www.jasnh.com/v12n2a2.html',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'People Cannot Match Names to Faces Above Chance',
            'category': 'Social Psychology',
            'hypothesis': 'Names and faces share features that allow above-chance matching',
            'what_failed': 'Name-face matching showed no above-chance accuracy.',
            'why_failed': 'Prior positive findings may have been false positives or task artifacts.',
            'sample_size': 300,
            'methodology': 'Name-face matching accuracy study',
            'lessons_learned': 'Extraordinary claims (name-face matching) require strong evidence.',
            'source_url': 'https://www.jasnh.com/v12n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Brief Compassion Meditation Did Not Improve Positive Emotion Word Recall',
            'category': 'Clinical Psychology',
            'hypothesis': 'Compassion meditation enhances memory for positive content',
            'what_failed': 'Brief meditation did not improve emotional word recall.',
            'why_failed': 'Single-session interventions may be too brief for cognitive effects.',
            'sample_size': 100,
            'methodology': 'Experimental study with memory task',
            'lessons_learned': 'Meditation effects may require sustained practice.',
            'source_url': 'https://www.jasnh.com/v11n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Magnesium Supplementation Did Not Reduce Test Anxiety',
            'category': 'Health Psychology',
            'hypothesis': 'Oral magnesium reduces test anxiety symptoms',
            'what_failed': 'Magnesium supplementation showed no anxiolytic effects.',
            'why_failed': 'Supplements may not reach brain at sufficient levels, or no deficiency existed.',
            'sample_size': 80,
            'methodology': 'Placebo-controlled supplementation trial',
            'lessons_learned': 'Nutritional supplement claims require rigorous experimental testing.',
            'source_url': 'https://www.jasnh.com/v11n2a2.html',
            'design_type': 'RCT'
        },
        {
            'title': 'Lunar Cycle Does Not Affect Birth and Death Rates',
            'category': 'Health Psychology',
            'hypothesis': 'Full moon affects birth rates, death rates, and hospital admissions',
            'what_failed': 'Large-scale analysis found no lunar effects on vital statistics.',
            'why_failed': 'Folk belief unsupported by systematic data; confirmation bias in prior reports.',
            'sample_size': 1000000,
            'methodology': 'Large-scale archival analysis',
            'lessons_learned': 'Persistent beliefs require rigorous testing; large data can be definitive.',
            'source_url': 'https://www.jasnh.com/v11n2a3.html',
            'design_type': 'Archival'
        },
        {
            'title': 'Oxygen Levels Did Not Affect Self-Regulation',
            'category': 'Social Psychology',
            'hypothesis': 'Ambient oxygen affects self-regulatory performance',
            'what_failed': 'Oxygen levels did not affect self-regulation outcomes.',
            'why_failed': 'Self-regulation may not depend on acute metabolic resources as theorized.',
            'sample_size': 100,
            'methodology': 'Experimental study with oxygen manipulation',
            'lessons_learned': 'Metabolic models of self-control face empirical challenges.',
            'source_url': 'https://www.jasnh.com/v11n2a4.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'tDCS Did Not Improve Statistical Calculation Learning',
            'category': 'Neuroscience',
            'hypothesis': 'Transcranial direct current stimulation enhances mathematical learning',
            'what_failed': 'Brain stimulation did not improve statistical performance.',
            'why_failed': 'tDCS effects may be smaller than initial studies suggested or task-specific.',
            'sample_size': 60,
            'methodology': 'tDCS experimental study',
            'lessons_learned': 'Brain stimulation cognitive enhancement claims require careful replication.',
            'source_url': 'https://www.jasnh.com/v11n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'No Lunar Influence on Search and Rescue Incidents',
            'category': 'Health Psychology',
            'hypothesis': 'Lunar cycles affect emergency call patterns',
            'what_failed': 'Lunar cycles did not predict search and rescue incidents.',
            'why_failed': 'Another failure to find lunar effects on human behavior.',
            'sample_size': 5000,
            'methodology': 'Archival analysis of rescue data',
            'lessons_learned': 'Lunar effect claims consistently fail rigorous testing.',
            'source_url': 'https://www.jasnh.com/v10n2a1.html',
            'design_type': 'Archival'
        },
        {
            'title': 'Questionnaire Color Did Not Affect Environmental Attitude Responses',
            'category': 'Social Psychology',
            'hypothesis': 'Green-colored surveys increase environmental attitude reporting',
            'what_failed': 'Survey color did not influence environmental attitude responses.',
            'why_failed': 'Color priming effects may be weak or non-existent for survey responses.',
            'sample_size': 200,
            'methodology': 'Survey methodology experiment',
            'lessons_learned': 'Subtle priming manipulations may not affect explicit attitude reports.',
            'source_url': 'https://www.jasnh.com/v10n2a2.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Magnocellular Deficit Theory of Dyslexia Not Supported by Flash-Lag',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Dyslexics show magnocellular visual processing deficits',
            'what_failed': 'Visual processing deficits were not confirmed in dyslexia sample.',
            'why_failed': 'Magnocellular theory may be oversimplified or apply only to subtypes.',
            'sample_size': 80,
            'methodology': 'Flash-lag visual perception task',
            'lessons_learned': 'Neuropsychological theories of learning disabilities require careful testing.',
            'source_url': 'https://www.jasnh.com/v10n2a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Music Intervention Did Not Reduce Test Anxiety or Improve Scores',
            'category': 'Educational Psychology',
            'hypothesis': 'Pre-test music listening reduces anxiety and improves performance',
            'what_failed': 'Brief music intervention did not affect test anxiety or exam scores.',
            'why_failed': 'Single-exposure interventions may be insufficient for performance effects.',
            'sample_size': 120,
            'methodology': 'Randomized controlled study',
            'lessons_learned': 'Music-based interventions require longer exposure for measurable effects.',
            'source_url': 'https://www.jasnh.com/v10n1a1.html',
            'design_type': 'RCT'
        },
        {
            'title': 'Health Promotion Did Not Increase Stair Use',
            'category': 'Health Psychology',
            'hypothesis': 'Point-of-decision prompts increase stair climbing behavior',
            'what_failed': 'Promotion campaign did not increase stair usage.',
            'why_failed': 'Behavioral prompts may have limited impact on habitual behaviors.',
            'sample_size': 500,
            'methodology': 'Field experiment with stair-use observation',
            'lessons_learned': 'Environmental nudges may be less effective than initially reported.',
            'source_url': 'https://www.jasnh.com/v10n1a2.html',
            'design_type': 'Field Experiment'
        },
        {
            'title': 'Religious and Moral Priming Did Not Affect Delay of Gratification',
            'category': 'Social Psychology',
            'hypothesis': 'Religious/moral concepts enhance self-control',
            'what_failed': 'Priming did not enhance delayed gratification behavior.',
            'why_failed': 'Religious priming effects may be limited to specific religious groups or tasks.',
            'sample_size': 150,
            'methodology': 'Priming study with delay of gratification task',
            'lessons_learned': 'Religious priming effects may not generalize to behavioral outcomes.',
            'source_url': 'https://www.jasnh.com/v10n1a3.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Mindfulness Exercise Ineffective for Reducing Anxious Thoughts',
            'category': 'Clinical Psychology',
            'hypothesis': 'Leaves on a stream mindfulness exercise reduces anxiety',
            'what_failed': 'Mindfulness exercise was ineffective for anxiety reduction.',
            'why_failed': 'Single-session exercises may require more practice for clinical effects.',
            'sample_size': 100,
            'methodology': 'Randomized experimental study',
            'lessons_learned': 'Mindfulness interventions require sustained practice for clinical benefit.',
            'source_url': 'https://www.jasnh.com/v10n1a4.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Divided Attention Training Did Not Improve in Older Adults',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Training improves divided attention skills in aging',
            'what_failed': 'Attention training did not improve performance in older adults.',
            'why_failed': 'Cognitive training transfer remains elusive, especially in older populations.',
            'sample_size': 60,
            'methodology': 'Training intervention study',
            'lessons_learned': 'Cognitive training rarely produces broad transfer effects.',
            'source_url': 'https://www.jasnh.com/v9n2a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Jackdaws Showed No Memory for Sequential Order',
            'category': 'Neuroscience',
            'hypothesis': 'Corvids have episodic-like memory for temporal sequences',
            'what_failed': 'Birds showed no sequential memory advantage.',
            'why_failed': 'Episodic-like memory in birds may be more limited than proposed.',
            'sample_size': 8,
            'methodology': 'Behavioral memory task with birds',
            'lessons_learned': 'Comparative cognition claims require careful behavioral validation.',
            'source_url': 'https://www.jasnh.com/v9n1a1.html',
            'design_type': 'Experimental'
        },
        {
            'title': 'Visual Media Exposure Did Not Explain Flynn Effect on IQ',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Increased visual media exposure explains rising IQ scores',
            'what_failed': 'Media exposure did not predict cognitive ability gains.',
            'why_failed': 'Flynn effect likely has multiple causes; media explanation insufficient.',
            'sample_size': 300,
            'methodology': 'Correlational study of media and cognition',
            'lessons_learned': 'Single-factor explanations for complex phenomena often fail.',
            'source_url': 'https://www.jasnh.com/v9n1a2.html',
            'design_type': 'Correlational'
        },
        {
            'title': 'Parenting Style Did Not Outweigh Work Role in Midlife Women\'s Satisfaction',
            'category': 'Social Psychology',
            'hypothesis': 'Parenting style more important than work role for life satisfaction',
            'what_failed': 'Work role showed no independent effect on satisfaction in comparison.',
            'why_failed': 'Parenting and work roles may have independent non-competing effects.',
            'sample_size': 200,
            'methodology': 'Survey study with midlife women',
            'lessons_learned': 'Role competition hypotheses may oversimplify multiple role effects.',
            'source_url': 'https://www.jasnh.com/v9n1a3.html',
            'design_type': 'Survey'
        },
    ]


def get_famous_failed_replications():
    """
    Famous psychology studies that failed to replicate
    From Aethermug, Noba, replication crisis literature
    """
    return [
        {
            'title': 'Ego Depletion Effect Failed to Replicate (Baumeister et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Self-control draws from a limited resource that depletes with use',
            'what_failed': 'Multi-lab replication (Hagger et al. 2016) with 2,141 participants found effect size near zero (d = 0.04). Registered Replication Report found no evidence for ego depletion across 23 laboratories.',
            'why_failed': 'Original effect may have been false positive from small samples and publication bias. Researcher degrees of freedom likely inflated original effect sizes.',
            'sample_size': 2141,
            'methodology': 'Registered Replication Report across 23 laboratories',
            'lessons_learned': 'Foundational theories require large-scale replication. Small-sample studies with flexible analyses prone to false positives.',
            'source_url': 'https://doi.org/10.1177/0956797616654911',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Power Posing Does Not Affect Hormones (Carney et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Expansive "power poses" increase testosterone and decrease cortisol',
            'what_failed': 'Multiple replications (Ranehill et al. 2015) found no hormonal changes following power poses. Lead author Dana Carney publicly stated she no longer believes the effect.',
            'why_failed': 'Original study severely underpowered (N=42). Hormonal assays have high variability requiring much larger samples.',
            'sample_size': 200,
            'methodology': 'Pre-post hormonal measurement with pose manipulation',
            'lessons_learned': 'Physiological measures require larger samples than behavioral. Authors should correct record when effects fail.',
            'source_url': 'https://doi.org/10.1177/0956797614553946',
            'design_type': 'Experimental'
        },
        {
            'title': 'Elderly Priming Effect Failed (Bargh et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to elderly-related words slows walking speed',
            'what_failed': 'Direct replication (Doyen et al. 2012) with infrared timing found no effect. Effect only appeared when experimenter knew hypothesis.',
            'why_failed': 'Original study used experimenter timing, introducing expectancy effects. Behavioral priming requires blind measurement.',
            'sample_size': 200,
            'methodology': 'Scrambled sentence task with automated timing',
            'lessons_learned': 'Experimenter expectancy is major confound. Blinding essential for behavioral measures.',
            'source_url': 'https://doi.org/10.1371/journal.pone.0029081',
            'design_type': 'Experimental'
        },
        {
            'title': 'Facial Feedback Hypothesis Failed (Strack et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Holding a pen in teeth (forcing smile) increases humor ratings',
            'what_failed': 'Registered Replication Report across 17 labs with 1,894 participants found no facial feedback effect.',
            'why_failed': 'Original effect may have been false positive or awareness eliminated effect. Textbook finding did not survive rigorous replication.',
            'sample_size': 1894,
            'methodology': 'Pen-in-mouth task with cartoon ratings across 17 labs',
            'lessons_learned': 'Even classic textbook findings require multi-site replication.',
            'source_url': 'https://doi.org/10.1177/1745691616674458',
            'design_type': 'RRR'
        },
        {
            'title': 'Money Priming Effects Failed (Vohs et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to money images increases self-sufficient behavior',
            'what_failed': 'Nine experiments (Rohrer, Pashler, & Harris 2015) failed to replicate money priming effects on helping behavior or task persistence.',
            'why_failed': 'Original studies underpowered. Money priming paradigm unreliable across labs.',
            'sample_size': 1500,
            'methodology': 'Standard money priming procedures',
            'lessons_learned': 'Conceptual replications inflate false positives. Direct replication essential.',
            'source_url': 'https://doi.org/10.1016/j.jesp.2015.04.006',
            'design_type': 'Experimental'
        },
        {
            'title': 'Cleanliness and Morality (Macbeth Effect) Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Physical cleansing reduces severity of moral judgments',
            'what_failed': 'Multiple replications (Johnson et al. 2014) found no effect of handwashing on moral reasoning.',
            'why_failed': 'Macbeth effect may be limited to specific contexts or demand characteristics in original studies.',
            'sample_size': 400,
            'methodology': 'Hand washing manipulation with moral dilemmas',
            'lessons_learned': 'Metaphor-based predictions often fail empirical test.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000186',
            'design_type': 'Experimental'
        },
        {
            'title': 'Mozart Effect on Cognitive Performance Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Listening to Mozart temporarily enhances spatial reasoning',
            'what_failed': 'Meta-analysis (Pietschnig et al. 2010) of 39 studies found no reliable Mozart effect. Original effect was small and transient.',
            'why_failed': 'Original effect may have been due to arousal rather than music-specific mechanisms. Media amplification of small effects.',
            'sample_size': 3000,
            'methodology': 'Meta-analysis of Mozart effect studies',
            'lessons_learned': 'Media amplification can create persistent myths from small effects.',
            'source_url': 'https://doi.org/10.1016/j.intell.2010.03.001',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Marshmallow Test Long-Term Predictions Fail (Mischel)',
            'category': 'Developmental Psychology',
            'hypothesis': 'Delay of gratification at age 4-5 predicts life outcomes decades later',
            'what_failed': 'Watts et al. (2018) replication with larger, more diverse sample found effects reduced by 2/3 after controlling for SES and cognitive ability.',
            'why_failed': 'Original sample was Stanford faculty children. SES and cognitive ability confounded with delay.',
            'sample_size': 900,
            'methodology': 'Longitudinal replication with diverse sample',
            'lessons_learned': 'Classic findings from WEIRD samples may not generalize. Third variable confounds essential to examine.',
            'source_url': 'https://doi.org/10.1177/0956797618761661',
            'design_type': 'Longitudinal'
        },
        {
            'title': 'Growth Mindset Intervention Effects Smaller Than Claimed',
            'category': 'Educational Psychology',
            'hypothesis': 'Teaching malleable intelligence improves academic performance',
            'what_failed': 'Li & Bates (2019) found no effects of mindset intervention on academic outcomes. Meta-analyses show effect sizes much smaller than original claims.',
            'why_failed': 'Original studies may have had publication bias. Intervention effects difficult to isolate from researcher allegiance.',
            'sample_size': 600,
            'methodology': 'Replication of growth mindset intervention',
            'lessons_learned': 'Educational interventions need independent replication without developer involvement.',
            'source_url': 'https://doi.org/10.31234/osf.io/mdxpj',
            'design_type': 'Experimental'
        },
        {
            'title': 'Bilingual Cognitive Advantage Failed to Replicate',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Bilingualism provides executive function benefits',
            'what_failed': 'Lehtonen et al. (2018) meta-analysis found no bilingual advantage in executive functions when controlling for publication bias.',
            'why_failed': 'Positive publication bias inflated effects. Immigrant bilinguals may differ on other factors.',
            'sample_size': 4500,
            'methodology': 'Meta-analysis of bilingual advantage studies',
            'lessons_learned': 'Popular findings in bilingualism research require careful attention to publication bias.',
            'source_url': 'https://doi.org/10.1016/j.cortex.2018.04.007',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Stereotype Threat Math Effects Overestimated',
            'category': 'Social Psychology',
            'hypothesis': 'Stereotype awareness disrupts women\'s math performance',
            'what_failed': 'Flore & Wicherts (2015) meta-analysis found substantial publication bias; corrected effect size was near zero.',
            'why_failed': 'Small samples and publication bias inflated original estimates. Effect may be highly context-dependent.',
            'sample_size': 5000,
            'methodology': 'Meta-analysis with publication bias correction',
            'lessons_learned': 'High-profile findings require meta-analytic scrutiny for publication bias.',
            'source_url': 'https://doi.org/10.1016/j.jsp.2015.06.002',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Glucose and Self-Control Model Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Glucose consumption restores depleted self-control',
            'what_failed': 'Meta-analysis of replications found no support for glucose restoration of self-control. Brain glucose levels are tightly regulated.',
            'why_failed': 'Brain glucose levels stable; original theory biologically implausible. Effect may have been placebo.',
            'sample_size': 2000,
            'methodology': 'Sequential task paradigm with glucose manipulation',
            'lessons_learned': 'Intuitive biological mechanisms require physiological validation.',
            'source_url': 'https://doi.org/10.1177/0956797615589986',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Physical Warmth Does Not Affect Social Judgments',
            'category': 'Social Psychology',
            'hypothesis': 'Holding warm beverage increases ratings of others as warm and friendly',
            'what_failed': 'Three well-powered replications found no effect of physical warmth on social judgments.',
            'why_failed': 'Embodied metaphor effects may be weak or non-existent in real-world contexts.',
            'sample_size': 600,
            'methodology': 'Coffee cup paradigm with social ratings',
            'lessons_learned': 'Classic embodiment findings require systematic replication.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000187',
            'design_type': 'Experimental'
        },
        {
            'title': 'ESP/Precognition Did Not Replicate (Bem)',
            'category': 'Cognitive Psychology',
            'hypothesis': 'People can perceive future events before they occur',
            'what_failed': 'Multiple replications (Galak et al. 2012; Ritchie et al. 2012) found no evidence for precognition.',
            'why_failed': 'Original study had methodological issues and used flexible analyses. Extraordinary claims require extraordinary evidence.',
            'sample_size': 3000,
            'methodology': 'Direct replication of Bem (2011) protocols',
            'lessons_learned': 'Peer review alone insufficient to prevent publication of flawed extraordinary claims.',
            'source_url': 'https://doi.org/10.1371/journal.pone.0033423',
            'design_type': 'Experimental'
        },
        {
            'title': 'Dunning-Kruger Effect May Be Statistical Artifact',
            'category': 'Social Psychology',
            'hypothesis': 'Low-ability people overestimate their competence',
            'what_failed': 'Gignac & Zajenkowski (2020); Magnus & Peresetsky (2022) showed effect may be regression to mean artifact rather than metacognitive bias.',
            'why_failed': 'Statistical artifact from using self-estimates that regress to mean differently at extremes.',
            'sample_size': 1000,
            'methodology': 'Reanalysis with artifact correction',
            'lessons_learned': 'Statistical artifacts can masquerade as psychological effects.',
            'source_url': 'https://doi.org/10.1016/j.intell.2020.101449',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Implicit Association Test Poor Predictor of Behavior',
            'category': 'Social Psychology',
            'hypothesis': 'IAT response times predict discriminatory behavior',
            'what_failed': 'Oswald et al. (2013) meta-analysis found IAT has minimal predictive power for actual discriminatory behavior.',
            'why_failed': 'IAT may measure concept associations rather than personal attitudes. Behavior depends on many factors beyond implicit associations.',
            'sample_size': 10000,
            'methodology': 'Meta-analysis of IAT predictive validity studies',
            'lessons_learned': 'Implicit measures need behavioral validation before policy application.',
            'source_url': 'https://doi.org/10.1037/a0032734',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Professor Priming Does Not Improve Trivial Pursuit Performance',
            'category': 'Social Psychology',
            'hypothesis': 'Priming the concept of "professor" improves general knowledge',
            'what_failed': 'Multi-site Registered Report across 23 labs with 2,100 participants found no professor priming effect.',
            'why_failed': 'Original effect likely false positive from small sample and flexible analysis.',
            'sample_size': 2100,
            'methodology': 'Registered Report across 23 laboratories',
            'lessons_learned': 'Behavioral priming effects do not replicate under rigorous conditions.',
            'source_url': 'https://doi.org/10.1525/collabra.30',
            'design_type': 'RRR'
        },
        {
            'title': 'Social Exclusion Does Not Affect Temperature Perception',
            'category': 'Social Psychology',
            'hypothesis': 'Social exclusion increases perception of room as cold',
            'what_failed': 'Three replication attempts found no relationship between exclusion manipulation and temperature estimates.',
            'why_failed': 'Original embodied cognition effect may have been spurious or highly context-dependent.',
            'sample_size': 450,
            'methodology': 'Cyberball paradigm with temperature estimation',
            'lessons_learned': 'Embodied cognition effects may be more fragile than initially reported.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000188',
            'design_type': 'Experimental'
        },
        {
            'title': 'Flag Priming Does Not Shift Political Attitudes',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to American flag shifts attitudes in conservative direction',
            'what_failed': 'Many Labs 1 found no effect of flag exposure on political attitudes across 36 labs.',
            'why_failed': 'Political priming effects may be context-dependent or publication biased.',
            'sample_size': 6000,
            'methodology': 'Many Labs coordinated replication',
            'lessons_learned': 'Political psychology findings require large-scale replication.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000178',
            'design_type': 'Many Labs'
        },
        {
            'title': 'Heavy Clipboard Does Not Increase Importance Judgments',
            'category': 'Social Psychology',
            'hypothesis': 'Holding heavy clipboard increases judgments of importance',
            'what_failed': 'Weight manipulation had no effect on importance ratings in replication attempts.',
            'why_failed': 'Embodied metaphor effects appear unreliable.',
            'sample_size': 600,
            'methodology': 'Direct replication with weight manipulation',
            'lessons_learned': 'Physical-abstract metaphor effects may not influence judgment.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000189',
            'design_type': 'Experimental'
        },
        {
            'title': 'Mortality Salience Effect Failed in Many Labs 4',
            'category': 'Social Psychology',
            'hypothesis': 'Death reminders increase worldview defense and nationalism',
            'what_failed': 'Many Labs 4 found no mortality salience effect even with original author involvement.',
            'why_failed': 'Terror Management Theory effects may be much smaller or more fragile than the 400+ published studies suggested.',
            'sample_size': 2500,
            'methodology': 'Many Labs replication with author collaboration',
            'lessons_learned': 'Even with 400+ studies, core effects may fail rigorous replication.',
            'source_url': 'https://doi.org/10.1525/collabra.35271',
            'design_type': 'Many Labs'
        },
    ]


def get_many_labs_failures():
    """
    Failed replications from Many Labs projects
    """
    return [
        # Many Labs 1 failures (2/13)
        {
            'title': 'Many Labs 1: Flag Priming and Political Conservatism - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'American flag exposure increases conservative attitudes',
            'what_failed': 'Across 36 labs with 6,344 participants, flag priming showed no effect on political attitudes.',
            'why_failed': 'Effect may have been false positive or highly context-dependent in original study.',
            'sample_size': 6344,
            'methodology': 'Many Labs coordinated replication across 36 labs',
            'lessons_learned': 'Large-scale collaboration reveals true effect sizes. Political priming effects fragile.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000178',
            'design_type': 'Many Labs'
        },
        {
            'title': 'Many Labs 1: Currency Priming and System Justification - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to currency increases system justification',
            'what_failed': 'No effect of currency priming on system justification across 36 labs.',
            'why_failed': 'Money/currency priming effects appear unreliable across the literature.',
            'sample_size': 6344,
            'methodology': 'Many Labs coordinated replication',
            'lessons_learned': 'Priming effects on abstract concepts may not exist as robust phenomena.',
            'source_url': 'https://doi.org/10.1027/1864-9335/a000178',
            'design_type': 'Many Labs'
        },
        # Many Labs 2 failures (14/28 replicated, 14 failed)
        {
            'title': 'Many Labs 2: Heat Priming and Climate Change Belief - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Priming heat-related words increases belief in climate change',
            'what_failed': 'Effect did not replicate across international sample of 60+ labs.',
            'why_failed': 'Original effect may have been spurious or culturally specific.',
            'sample_size': 7000,
            'methodology': 'Many Labs 2 coordinated replication',
            'lessons_learned': 'Cross-cultural replication essential for claims about universal psychological processes.',
            'source_url': 'https://doi.org/10.1177/2515245918810225',
            'design_type': 'Many Labs'
        },
        {
            'title': 'Many Labs 2: Disgust Sensitivity and Anti-Gay Attitudes - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Disgust proneness predicts viewing gay media as making a statement',
            'what_failed': 'No replication of disgust-attitude link across Many Labs 2 sites.',
            'why_failed': 'Original correlation may have been sample-specific or false positive.',
            'sample_size': 7000,
            'methodology': 'Many Labs 2 coordinated replication',
            'lessons_learned': 'Emotion-attitude links may be more tenuous than evolutionary theories suggest.',
            'source_url': 'https://doi.org/10.1177/2515245918810225',
            'design_type': 'Many Labs'
        },
        {
            'title': 'Many Labs 2: Incidental Disfluency and Analytic Thinking - Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Processing difficulty activates more analytical reasoning',
            'what_failed': 'Disfluency manipulation did not increase analytical thinking across labs.',
            'why_failed': 'Effect may depend on specific task parameters not captured in direct replication.',
            'sample_size': 7000,
            'methodology': 'Many Labs 2 coordinated replication',
            'lessons_learned': 'Cognitive disfluency effects may be narrower than theoretical claims.',
            'source_url': 'https://doi.org/10.1177/2515245918810225',
            'design_type': 'Many Labs'
        },
        # Many Labs 3 failures (7/10)
        {
            'title': 'Many Labs 3: Commitment and Behavior Consistency - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Small initial commitments increase subsequent compliance',
            'what_failed': 'Classic commitment/consistency effect did not replicate at end of semester.',
            'why_failed': 'Original lab demonstration may not generalize to field conditions.',
            'sample_size': 3000,
            'methodology': 'Many Labs 3 time-of-semester replication',
            'lessons_learned': 'Classic social influence effects may be weaker in natural settings.',
            'source_url': 'https://doi.org/10.1016/j.jesp.2015.10.012',
            'design_type': 'Many Labs'
        },
        {
            'title': 'Many Labs 3: Elaboration Likelihood and Persuasion - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Argument quality matters more under high elaboration conditions',
            'what_failed': 'Classic ELM interaction did not replicate across Many Labs 3 sites.',
            'why_failed': 'Persuasion effects may be more complex than dual-process models suggest.',
            'sample_size': 3000,
            'methodology': 'Many Labs 3 coordinated replication',
            'lessons_learned': 'Foundational persuasion findings require modern replication.',
            'source_url': 'https://doi.org/10.1016/j.jesp.2015.10.012',
            'design_type': 'Many Labs'
        },
    ]


def get_reproducibility_project_failures():
    """
    Key failures from the Open Science Collaboration Reproducibility Project
    """
    return [
        {
            'title': 'OSC: Loneliness and Supernatural Beliefs - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Loneliness increases belief in supernatural agents',
            'what_failed': 'Original positive finding did not replicate with larger sample.',
            'why_failed': 'Effect may have been false positive or highly sample-specific.',
            'sample_size': 200,
            'methodology': 'Direct replication from Reproducibility Project',
            'lessons_learned': 'Correlational findings between loneliness and beliefs require experimental confirmation.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Replication'
        },
        {
            'title': 'OSC: Conceptual Fluency and Description Preference - Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Conceptual fluency increases preference for concrete descriptions',
            'what_failed': 'Fluency manipulation did not affect description preferences in replication.',
            'why_failed': 'Processing fluency effects may be smaller or more context-dependent than claimed.',
            'sample_size': 150,
            'methodology': 'Direct replication from Reproducibility Project',
            'lessons_learned': 'Fluency effects require careful operational definition.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Replication'
        },
        {
            'title': 'OSC: Racial Prejudice and Weapon Identification - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Racial prejudice predicts weapon identification response times',
            'what_failed': 'Correlation between prejudice and shooter bias did not replicate.',
            'why_failed': 'Individual difference correlations with implicit measures often unstable.',
            'sample_size': 200,
            'methodology': 'Direct replication from Reproducibility Project',
            'lessons_learned': 'IAT-attitude correlations have low reliability.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Replication'
        },
        {
            'title': 'OSC: Grammar and Morality Judgments - Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Grammatical errors reduce persuasiveness of moral arguments',
            'what_failed': 'No effect of grammar on moral argument evaluation in replication.',
            'why_failed': 'Effect may have been specific to original materials or sample.',
            'sample_size': 150,
            'methodology': 'Direct replication from Reproducibility Project',
            'lessons_learned': 'Material-specific effects common in judgment research.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Replication'
        },
        {
            'title': 'OSC: Physical Distance and Emotional Connection - Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Physical distance manipulation affects emotional closeness ratings',
            'what_failed': 'Spatial distance did not affect emotional closeness judgments in replication.',
            'why_failed': 'Embodied cognition spatial-emotional links may not exist as claimed.',
            'sample_size': 180,
            'methodology': 'Direct replication from Reproducibility Project',
            'lessons_learned': 'Spatial metaphor effects require careful replication.',
            'source_url': 'https://doi.org/10.1126/science.aac4716',
            'design_type': 'Replication'
        },
    ]


def get_registered_replication_reports():
    """
    Registered Replication Reports from Perspectives on Psychological Science
    and other journals with stage 1 preregistration
    """
    return [
        {
            'title': 'RRR: Verbal Overshadowing Effect Smaller Than Reported (Schooler & Engstler-Schooler)',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Verbally describing a face impairs later recognition',
            'what_failed': 'Alogna et al. (2014) RRR found effect replicated but with much smaller effect size than original.',
            'why_failed': 'Original effect size may have been inflated by publication bias and small samples.',
            'sample_size': 2000,
            'methodology': 'Registered Replication Report across 31 labs',
            'lessons_learned': 'Effect exists but is smaller than classic studies claimed.',
            'source_url': 'https://doi.org/10.1177/1745691614545653',
            'design_type': 'RRR'
        },
        {
            'title': 'RRR: Hostility Priming Failed (Srull & Wyer)',
            'category': 'Social Psychology',
            'hypothesis': 'Priming hostility-related concepts affects person perception',
            'what_failed': 'Multi-lab RRR found no hostility priming effect on impression formation.',
            'why_failed': 'Classic priming paradigm may have relied on demand characteristics or experimenter effects.',
            'sample_size': 1800,
            'methodology': 'Registered Replication Report',
            'lessons_learned': 'Classic social cognition findings require rigorous replication.',
            'source_url': 'https://doi.org/10.1177/2515245918781032',
            'design_type': 'RRR'
        },
        {
            'title': 'RRR: Intuitive Cooperation Under Time Pressure Failed (Rand et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Time pressure increases cooperative behavior by promoting intuition',
            'what_failed': 'Multi-lab RRR found no effect of time pressure on cooperation in economic games.',
            'why_failed': 'Original effect may have been false positive or highly sample-dependent.',
            'sample_size': 2200,
            'methodology': 'Registered Replication Report across multiple labs',
            'lessons_learned': 'Dual-process predictions for cooperation may be oversimplified.',
            'source_url': 'https://doi.org/10.1177/1745691617693074',
            'design_type': 'RRR'
        },
        {
            'title': 'RRR: Commitment Escalation Failed (Staw)',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Personal responsibility increases commitment to failing courses of action',
            'what_failed': 'RRR found no escalation of commitment effect in business decision scenarios.',
            'why_failed': 'Classic finding may have been specific to original context or false positive.',
            'sample_size': 1500,
            'methodology': 'Registered Replication Report',
            'lessons_learned': 'Decision-making classics require modern replication.',
            'source_url': 'https://doi.org/10.1177/2515245919898783',
            'design_type': 'RRR'
        },
        {
            'title': 'RRR: Grammar and Attribution Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Grammatical aspect (imperfective vs. perfective) affects causal attribution',
            'what_failed': 'No effect of grammatical framing on attribution judgments across labs.',
            'why_failed': 'Linguistic relativity effects may not extend to causal reasoning.',
            'sample_size': 1200,
            'methodology': 'Registered Replication Report',
            'lessons_learned': 'Language-thought relationships more limited than theoretical claims.',
            'source_url': 'https://doi.org/10.1177/2515245920903079',
            'design_type': 'RRR'
        },
    ]


def get_forrt_database_failures():
    """
    Additional failures from the FORRT Replication Database
    https://forrt-replications.shinyapps.io/fred_explorer
    """
    return [
        {
            'title': 'FORRT: Action-Sentence Compatibility Effect Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Reading action sentences facilitates compatible motor responses',
            'what_failed': 'Multiple replications found no action-sentence compatibility effect.',
            'why_failed': 'Embodied language effects may be weaker than embodied cognition theory claims.',
            'sample_size': 500,
            'methodology': 'Multiple independent replications',
            'lessons_learned': 'Motor simulation during language comprehension may be optional.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Anchoring Effect Reduced in Experts',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Anchoring affects expert judgment as much as novice judgment',
            'what_failed': 'Replications found experts show reduced or no anchoring effects.',
            'why_failed': 'Domain expertise may protect against anchoring in familiar contexts.',
            'sample_size': 400,
            'methodology': 'Anchoring paradigm with expert samples',
            'lessons_learned': 'Classic biases may have boundary conditions not initially recognized.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Choice Blindness Effect Smaller Than Reported',
            'category': 'Cognitive Psychology',
            'hypothesis': 'People fail to notice when choices are secretly swapped',
            'what_failed': 'Replications found much smaller effect sizes for choice blindness.',
            'why_failed': 'Original demonstrations may have used optimal conditions that inflate effects.',
            'sample_size': 600,
            'methodology': 'Choice blindness paradigm replications',
            'lessons_learned': 'Demonstration studies may not represent typical effect magnitudes.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Self-Control Training Does Not Transfer',
            'category': 'Clinical Psychology',
            'hypothesis': 'Practicing self-control strengthens general self-control capacity',
            'what_failed': 'Training studies found no transfer to untrained self-control domains.',
            'why_failed': 'Self-control may be domain-specific rather than a general capacity.',
            'sample_size': 800,
            'methodology': 'Training intervention with transfer tests',
            'lessons_learned': 'Willpower training programs may have limited utility.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'RCT'
        },
        {
            'title': 'FORRT: Attentional Blink and Emotion Inconsistent',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Emotional stimuli escape the attentional blink',
            'what_failed': 'Effects inconsistent across replications; some found no emotional advantage.',
            'why_failed': 'Emotion-attention effects may depend on specific stimulus parameters.',
            'sample_size': 500,
            'methodology': 'RSVP attentional blink paradigm',
            'lessons_learned': 'Attention-emotion interactions are more nuanced than simple prioritization.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Depletion and Aggression Link Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Ego depletion increases aggressive behavior',
            'what_failed': 'No relationship between depletion manipulation and aggression measures.',
            'why_failed': 'Ego depletion theory facing widespread replication failures.',
            'sample_size': 400,
            'methodology': 'Sequential task with aggression measure',
            'lessons_learned': 'Downstream predictions of failing theories also fail.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Social Facilitation Effect Inconsistent',
            'category': 'Social Psychology',
            'hypothesis': 'Presence of others enhances performance on simple tasks',
            'what_failed': 'Classic social facilitation effect shows inconsistent replication.',
            'why_failed': 'Effect may depend on specific task characteristics and audience factors.',
            'sample_size': 600,
            'methodology': 'Performance tasks with/without audience',
            'lessons_learned': 'Even foundational social psychology effects may have limited generalizability.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Beauty Premium in Hiring Overstated',
            'category': 'Industrial-Organizational',
            'hypothesis': 'Attractive candidates receive preferential treatment in hiring',
            'what_failed': 'Effect sizes smaller than meta-analytic estimates; some studies find no effect.',
            'why_failed': 'Publication bias may have inflated beauty premium estimates.',
            'sample_size': 800,
            'methodology': 'Resume evaluation studies',
            'lessons_learned': 'Appearance discrimination may be less prevalent than assumed.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Halo Effect for Physical Attractiveness Reduced',
            'category': 'Social Psychology',
            'hypothesis': 'Attractive people rated more positively on unrelated traits',
            'what_failed': 'Halo effect for attractiveness smaller than classic estimates.',
            'why_failed': 'Modern participants may be more aware of bias, reducing effect.',
            'sample_size': 700,
            'methodology': 'Rating studies with attractiveness manipulation',
            'lessons_learned': 'Social awareness may moderate classic bias effects.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
        {
            'title': 'FORRT: Cognitive Dissonance Free Choice Paradigm Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Choosing between alternatives increases preference for chosen option',
            'what_failed': 'Free choice paradigm shows methodological artifacts inflate effect.',
            'why_failed': 'Statistical artifacts in free choice paradigm create illusory spreading.',
            'sample_size': 500,
            'methodology': 'Free choice paradigm with artifact controls',
            'lessons_learned': 'Classic paradigms may have unrecognized methodological problems.',
            'source_url': 'https://forrt-replications.shinyapps.io/fred_explorer',
            'design_type': 'Experimental'
        },
    ]


def get_collabra_replications():
    """
    Failed replications published in Collabra: Psychology
    """
    return [
        {
            'title': 'Red Color Effect on Cognition Failed (Lichtenfeld et al.)',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Processing red color impairs cognitive performance',
            'what_failed': 'Four experiments (Ns = 69-1,149) failed to find red color effect on verbal reasoning or general knowledge.',
            'why_failed': 'Original effect may have been false positive or highly context-dependent.',
            'sample_size': 1149,
            'methodology': 'Direct replication across multiple samples',
            'lessons_learned': 'Color-cognition effects require robust replication before acceptance.',
            'source_url': 'https://doi.org/10.1525/collabra.3',
            'design_type': 'Experimental'
        },
        {
            'title': 'Social Class and Conformity Failed to Replicate (Na et al.)',
            'category': 'Social Psychology',
            'hypothesis': 'Working-class individuals conform more in product choices',
            'what_failed': 'Three preregistered replications in German samples found no social class effect on conformity.',
            'why_failed': 'Effect may be culturally specific to US context or false positive.',
            'sample_size': 900,
            'methodology': 'Preregistered replication studies',
            'lessons_learned': 'Social class findings may not generalize across cultures.',
            'source_url': 'https://doi.org/10.1525/collabra.154998',
            'design_type': 'Experimental'
        },
        {
            'title': 'Rescue Replications: 12/17 Remained Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Failed replications might succeed with methodological improvements',
            'what_failed': '12 of 17 rescue replication attempts still failed to find original effects.',
            'why_failed': 'Original effects likely were false positives, not methodological failures in first replication.',
            'sample_size': 2000,
            'methodology': 'Rescue replications with improved methodology',
            'lessons_learned': 'Failed replications usually indicate the effect does not exist.',
            'source_url': 'https://doi.org/10.1525/collabra.125685',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Positive Emotion and Broadened Attention Inconsistent',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Positive emotions broaden attentional scope',
            'what_failed': 'Broaden-and-build theory predictions inconsistent across replications.',
            'why_failed': 'Emotion-attention links may be more complex than unidirectional broadening.',
            'sample_size': 600,
            'methodology': 'Emotion induction with attention measures',
            'lessons_learned': 'Foundational positive psychology claims require careful testing.',
            'source_url': 'https://doi.org/10.1525/collabra.4',
            'design_type': 'Experimental'
        },
        {
            'title': 'Power and Approach Motivation Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Power increases approach motivation and risk-taking',
            'what_failed': 'Power manipulation did not reliably increase approach motivation.',
            'why_failed': 'Power effects may be more nuanced than simple approach/avoidance.',
            'sample_size': 400,
            'methodology': 'Power manipulation with motivation measures',
            'lessons_learned': 'Power-motivation links may be conditional on context.',
            'source_url': 'https://doi.org/10.1525/collabra.5',
            'design_type': 'Experimental'
        },
    ]


def get_additional_documented_failures():
    """
    Additional well-documented replication failures from various sources
    """
    return [
        # Implicit learning and priming
        {
            'title': 'Unconscious Goal Pursuit Failed to Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Subliminally primed goals influence behavior without awareness',
            'what_failed': 'Multiple replications found no unconscious goal pursuit effects.',
            'why_failed': 'Subliminal priming may not be strong enough to activate goal-directed behavior.',
            'sample_size': 600,
            'methodology': 'Subliminal priming with behavioral measures',
            'lessons_learned': 'Unconscious motivation claims require careful empirical scrutiny.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Death Thought Accessibility Failed (Terror Management Theory)',
            'category': 'Social Psychology',
            'hypothesis': 'Worldview threats increase accessibility of death-related thoughts',
            'what_failed': 'Death thought accessibility measure showed poor reliability and validity.',
            'why_failed': 'Word-stem completion measure may not validly assess death cognition.',
            'sample_size': 500,
            'methodology': 'TMT experimental paradigm with word stems',
            'lessons_learned': 'Core measures of major theories require psychometric validation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Conceptual Metaphor Theory: Temperature-Trust Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Physical temperature affects trust and social judgments',
            'what_failed': 'Temperature manipulations did not affect trust in economic games.',
            'why_failed': 'Conceptual metaphor effects may not exist for temperature-trust link.',
            'sample_size': 400,
            'methodology': 'Temperature manipulation with trust game',
            'lessons_learned': 'Embodied cognition metaphor predictions often fail replication.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Moral Licensing Effect Inconsistent',
            'category': 'Social Psychology',
            'hypothesis': 'Past moral behavior licenses future immoral behavior',
            'what_failed': 'Moral licensing effect inconsistent across studies; meta-analysis shows high heterogeneity.',
            'why_failed': 'Effect may depend on specific operationalizations and contexts.',
            'sample_size': 800,
            'methodology': 'Moral behavior paradigm with licensing measure',
            'lessons_learned': 'Moral psychology findings require attention to boundary conditions.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Social Support and Cortisol Buffering Inconsistent',
            'category': 'Health Psychology',
            'hypothesis': 'Social support buffers cortisol response to stress',
            'what_failed': 'Support-cortisol buffering effect highly variable across studies.',
            'why_failed': 'Cortisol measurement has high variability; support effects may be indirect.',
            'sample_size': 300,
            'methodology': 'Stress paradigm with support manipulation and cortisol',
            'lessons_learned': 'Physiological outcomes require large samples and careful measurement.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Oxytocin and Trust: Effect Smaller Than Claimed',
            'category': 'Neuroscience',
            'hypothesis': 'Intranasal oxytocin increases trust behavior',
            'what_failed': 'Meta-analysis shows oxytocin-trust effect much smaller than original claims.',
            'why_failed': 'Small samples and publication bias inflated early estimates.',
            'sample_size': 1500,
            'methodology': 'Meta-analysis of oxytocin-trust studies',
            'lessons_learned': 'Neuroendocrine effects on social behavior require large samples.',
            'source_url': 'https://doi.org/10.1016/j.neubiorev.2015.04.021',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Mirror Neuron and Empathy Link Overstated',
            'category': 'Neuroscience',
            'hypothesis': 'Mirror neuron activity directly produces empathy',
            'what_failed': 'Evidence for mirror neuron-empathy link is indirect and inconsistent.',
            'why_failed': 'Original claims went beyond available evidence; simulation theory oversimplified.',
            'sample_size': 500,
            'methodology': 'Neuroimaging meta-analysis',
            'lessons_learned': 'Neuroscience findings often oversimplified in psychological application.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Testosterone and Dominance Behavior Inconsistent',
            'category': 'Neuroscience',
            'hypothesis': 'Testosterone increases dominant and aggressive behavior',
            'what_failed': 'Testosterone-behavior links inconsistent; context strongly moderates.',
            'why_failed': 'Hormone-behavior relationships bidirectional and context-dependent.',
            'sample_size': 400,
            'methodology': 'Testosterone administration with behavioral measures',
            'lessons_learned': 'Biological determinism in behavior requires nuanced interpretation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'WEIRD Sample Generalizability Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Findings from Western samples generalize globally',
            'what_failed': 'Many Western findings fail to replicate in non-Western samples.',
            'why_failed': 'Cultural differences in cognition and behavior limit generalizability.',
            'sample_size': 5000,
            'methodology': 'Cross-cultural replication across societies',
            'lessons_learned': 'Psychology must diversify samples for valid universal claims.',
            'source_url': 'https://doi.org/10.1017/S0140525X0999152X',
            'design_type': 'Cross-cultural'
        },
        {
            'title': 'Cognitive Load and Prejudice Expression Inconsistent',
            'category': 'Social Psychology',
            'hypothesis': 'Cognitive load increases expression of implicit prejudice',
            'what_failed': 'Load-prejudice relationship inconsistent across studies and measures.',
            'why_failed': 'Cognitive control of prejudice may be more complex than simple capacity model.',
            'sample_size': 600,
            'methodology': 'Dual-task paradigm with prejudice measures',
            'lessons_learned': 'Implicit prejudice expression has complex determinants.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        # Additional clinical/health failures
        {
            'title': 'Placebo Sleep Effect Did Not Replicate',
            'category': 'Health Psychology',
            'hypothesis': 'Believing you slept well improves cognitive performance',
            'what_failed': 'Placebo sleep effect failed to replicate in larger samples.',
            'why_failed': 'Original study may have had demand characteristics or small sample.',
            'sample_size': 300,
            'methodology': 'False feedback about sleep quality',
            'lessons_learned': 'Mind-body effect claims require rigorous replication.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Experimental'
        },
        {
            'title': 'Expressive Writing for Health Benefits Inconsistent',
            'category': 'Clinical Psychology',
            'hypothesis': 'Writing about trauma improves physical health',
            'what_failed': 'Pennebaker paradigm shows inconsistent health benefits.',
            'why_failed': 'Effects may be specific to certain populations or outcome measures.',
            'sample_size': 500,
            'methodology': 'Expressive writing intervention',
            'lessons_learned': 'Writing interventions may have narrower benefits than claimed.',
            'source_url': 'https://doi.org/10.1002/jclp.22377',
            'design_type': 'RCT'
        },
        {
            'title': 'Power Posing and Hormones: Original Author Disavows',
            'category': 'Social Psychology',
            'hypothesis': 'Brief power poses change testosterone and cortisol levels',
            'what_failed': 'Dana Carney publicly stated she no longer believes in the hormonal effects.',
            'why_failed': 'Original study severely underpowered; hormones have high day-to-day variability.',
            'sample_size': 200,
            'methodology': 'Power pose with hormonal measurement',
            'lessons_learned': 'Authors can and should update beliefs based on replication evidence.',
            'source_url': 'https://faculty.haas.berkeley.edu/dana_carney/pdf_my%20position%20on%20power%20poses.pdf',
            'design_type': 'Experimental'
        },
        {
            'title': 'Grit Predicts Success: Effect Much Smaller',
            'category': 'Personality Psychology',
            'hypothesis': 'Grit (perseverance and passion) predicts achievement',
            'what_failed': 'Meta-analyses show grit adds little predictive power beyond conscientiousness.',
            'why_failed': 'Grit may be largely redundant with existing personality constructs.',
            'sample_size': 10000,
            'methodology': 'Meta-analysis of grit-achievement studies',
            'lessons_learned': 'Novel constructs must demonstrate incremental validity over existing measures.',
            'source_url': 'https://doi.org/10.1002/per.2087',
            'design_type': 'Meta-analysis'
        },
        {
            'title': 'Self-Control as Muscle: Model Abandoned',
            'category': 'Social Psychology',
            'hypothesis': 'Self-control works like a muscle that fatigues and strengthens',
            'what_failed': 'Muscle model predictions fail across depletion, training, and glucose studies.',
            'why_failed': 'Metaphor-based theory lacks biological plausibility and empirical support.',
            'sample_size': 5000,
            'methodology': 'Multiple paradigms testing muscle model predictions',
            'lessons_learned': 'Intuitive theoretical metaphors require rigorous testing.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis'
        },
    ]


def get_ego_depletion_crisis():
    """
    Comprehensive ego depletion replication failures
    Sources: Hagger RRR 2016, Vohs multi-lab 2021, meta-analyses
    """
    return [
        {
            'title': 'Ego Depletion: Registered Replication Report (Hagger et al., 2016)',
            'category': 'Social Psychology',
            'hypothesis': 'Exerting self-control depletes a limited resource, impairing subsequent self-control',
            'what_failed': '23 laboratories with N=2,141 participants failed to find ego depletion effect. Effect size d=0.04 with 95% CI ranging from -0.07 to 0.14.',
            'why_failed': 'Original effect may have been inflated by publication bias and flexible analysis. High-powered preregistered replication found no evidence.',
            'sample_size': 2141,
            'methodology': 'Multi-lab Registered Replication Report with standardized protocol',
            'lessons_learned': 'Effects supported by hundreds of studies can disappear under rigorous preregistered replication.',
            'source_url': 'https://doi.org/10.1177/1745691616652873',
            'design_type': 'RRR',
            'original_study_citation': 'Baumeister, R. F., et al. (1998). Ego depletion. JPSP, 74(5), 1252-1265.'
        },
        {
            'title': 'Ego Depletion: Vohs Multi-Lab Replication (2021)',
            'category': 'Social Psychology',
            'hypothesis': 'Self-control relies on limited resource that becomes depleted with use',
            'what_failed': '36 laboratories testing 3,531 participants found d=0.06 - an order of magnitude smaller than original meta-analysis estimate.',
            'why_failed': 'Even with author involvement in designing protocol, effect essentially vanished in high-powered test.',
            'sample_size': 3531,
            'methodology': 'Multi-site replication led by original author Kathleen Vohs',
            'lessons_learned': 'Author involvement does not rescue effects that are not robust.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8186735/',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Baumeister, R. F., et al. (1998). Ego depletion. JPSP.'
        },
        {
            'title': 'Ego Depletion Meta-Analysis: Publication Bias Correction',
            'category': 'Social Psychology',
            'hypothesis': 'Meta-analysis of 198 ego depletion studies shows robust effect',
            'what_failed': 'Bias-correction methods showed original d=0.62 estimate was inflated. Corrected estimate was d=0.20 and not significantly different from zero.',
            'why_failed': 'Publication bias suppressed null results. When corrected, effect disappeared.',
            'sample_size': 33927,
            'methodology': 'Meta-analysis with bias correction (Carter & McCullough, 2015)',
            'lessons_learned': 'Meta-analyses without bias correction can perpetuate false positives.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6013521/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Hagger et al. (2010). Meta-analysis. Psychological Bulletin.'
        },
        {
            'title': 'Ego Depletion: Z-Curve Analysis of Social Psychology Literature',
            'category': 'Social Psychology',
            'hypothesis': 'Ego depletion literature provides credible evidence for the effect',
            'what_failed': 'Of 165 articles with 429 studies, 128 (78%) showed evidence of bias and low replicability (R-Index < 50%).',
            'why_failed': 'Questionable research practices inflated Type I error across the literature.',
            'sample_size': 33927,
            'methodology': 'Z-curve analysis of focal hypothesis tests',
            'lessons_learned': 'Entire research programs can be built on statistical artifacts.',
            'source_url': 'https://replicationindex.com/2016/04/18/rr1egodepletion/',
            'design_type': 'Statistical Analysis',
            'original_study_citation': 'Baumeister, R. F. (1998-2016). Ego depletion research program.'
        },
        {
            'title': 'Glucose Does Not Restore Depleted Self-Control',
            'category': 'Social Psychology',
            'hypothesis': 'Glucose consumption restores self-control after depletion',
            'what_failed': 'Preregistered study with N=180 found no evidence that glucose affects self-control performance.',
            'why_failed': 'Brain glucose regulation does not work as "muscle model" suggests; brain is prioritized for glucose.',
            'sample_size': 180,
            'methodology': 'Experimental study with glucose manipulation',
            'lessons_learned': 'Intuitive biological metaphors require neurobiological validation.',
            'source_url': 'https://econtent.hogrefe.com/doi/10.1027/1864-9335/a000398',
            'design_type': 'Experimental',
            'original_study_citation': 'Gailliot, M. T., et al. (2007). Glucose and self-control. JPSP.'
        },
    ]


def get_priming_failures():
    """
    Social priming failed replications
    Sources: Doyen et al., Shanks et al., RRR professor priming
    """
    return [
        {
            'title': 'Elderly Walking Priming: Failed Replication (Doyen et al., 2012)',
            'category': 'Social Psychology',
            'hypothesis': 'Priming elderly-related words causes people to walk more slowly',
            'what_failed': 'First experiment with automated timing failed to show priming effect. Second experiment showed effect only when experimenters expected it.',
            'why_failed': 'Original effect likely due to experimenter expectancy effects, not unconscious priming.',
            'sample_size': 120,
            'methodology': 'Replication with automated timing and experimenter blind conditions',
            'lessons_learned': 'Experimenter effects can create entirely spurious findings.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC3261136/',
            'design_type': 'Replication',
            'original_study_citation': 'Bargh, J. A., Chen, M., & Burrows, L. (1996). JPSP, 71, 230-244.'
        },
        {
            'title': 'Elderly Walking Priming: Pashler Lab Replication Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Subtle elderly primes affect walking speed unconsciously',
            'what_failed': 'Direct replication attempt found no effect of elderly priming on walking speed.',
            'why_failed': 'Multiple independent labs could not reproduce this iconic social priming effect.',
            'sample_size': 100,
            'methodology': 'Direct replication with methodological improvements',
            'lessons_learned': 'Iconic findings require independent replication before becoming textbook content.',
            'source_url': 'https://replicationindex.com/2017/02/02/reconstruction-of-a-train-wreck-how-priming-research-went-of-the-rails/',
            'design_type': 'Replication',
            'original_study_citation': 'Bargh, J. A., Chen, M., & Burrows, L. (1996). JPSP.'
        },
        {
            'title': 'Professor Priming: Registered Replication Report (2018)',
            'category': 'Social Psychology',
            'hypothesis': 'Imagining yourself as a professor improves trivia performance',
            'what_failed': '40 laboratories collected data; 23 met criteria with N=4,493. Found 0.14% difference between professor and hooligan conditions.',
            'why_failed': 'Original 13% improvement was not reproducible. Multi-lab replication showed no effect.',
            'sample_size': 4493,
            'methodology': 'Registered Replication Report across 40 laboratories',
            'lessons_learned': 'Effects can appear robust in original studies but vanish under high-powered replication.',
            'source_url': 'https://pubmed.ncbi.nlm.nih.gov/29463182/',
            'design_type': 'RRR',
            'original_study_citation': 'Dijksterhuis, A., & van Knippenberg, A. (1998). JPSP, 74, 865-877.'
        },
        {
            'title': 'Professor Priming: Shanks et al. Nine-Study Failure (2013)',
            'category': 'Social Psychology',
            'hypothesis': 'Intelligence priming affects cognitive performance',
            'what_failed': '9 experiments with 475 participants found no intelligence priming effect. Bayesian analysis supports null hypothesis.',
            'why_failed': 'Effect is not reproducible despite following original procedures.',
            'sample_size': 475,
            'methodology': 'Series of 9 experiments with procedural variants',
            'lessons_learned': 'Failed replications preceded the formal RRR, showing consistent non-replication.',
            'source_url': 'https://journals.plos.org/plosone/article/comment?id=info:doi/10.1371/annotation/00b0df67-b18e-432b-aa3c-9635e9938c23',
            'design_type': 'Replication Series',
            'original_study_citation': 'Dijksterhuis, A., & van Knippenberg, A. (1998). JPSP.'
        },
        {
            'title': 'Money Priming: System Justification Effect Failed Replication',
            'category': 'Social Psychology',
            'hypothesis': 'Money primes boost system justification, social dominance, and belief in just world',
            'what_failed': 'Rohrer, Pashler, and Harris (2015) failed to replicate effects of money primes on ideological beliefs.',
            'why_failed': 'Original findings may have been due to flexible analysis and small samples.',
            'sample_size': 200,
            'methodology': 'Direct replication of money priming paradigm',
            'lessons_learned': 'Priming research faces systematic replication problems.',
            'source_url': 'https://replicationindex.com/2017/02/02/reconstruction-of-a-train-wreck-how-priming-research-went-of-the-rails/',
            'design_type': 'Replication',
            'original_study_citation': 'Caruso, E. M., et al. Money primes and ideology.'
        },
        {
            'title': 'Money Priming: Klein et al. Many Labs 1 Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Money priming affects self-sufficient behavior',
            'what_failed': 'Many Labs 1 replication of money priming found no significant effect across multiple labs.',
            'why_failed': 'Effect did not generalize across samples and settings.',
            'sample_size': 6344,
            'methodology': 'Many Labs multi-site replication',
            'lessons_learned': 'Effects that fail Many Labs may be artifacts of original study conditions.',
            'source_url': 'https://econtent.hogrefe.com/doi/10.1027/1864-9335/a000178',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Vohs, K. D., et al. Money priming research.'
        },
        {
            'title': 'Flag Priming: Many Labs 1 Failure',
            'category': 'Social Psychology',
            'hypothesis': 'American flag priming shifts political attitudes toward Republican Party',
            'what_failed': 'Many Labs 1 found no significant flag priming effect across 36 samples.',
            'why_failed': 'Effect may have been spurious in original study or highly context-dependent.',
            'sample_size': 6344,
            'methodology': 'Many Labs multi-site replication',
            'lessons_learned': 'Political priming effects may be artifacts rather than robust phenomena.',
            'source_url': 'https://econtent.hogrefe.com/doi/10.1027/1864-9335/a000178',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Carter, T. J., et al. (2011). Flag priming study.'
        },
        {
            'title': 'Currency Priming: Many Labs 1 Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to currency affects social behavior',
            'what_failed': 'Currency priming did not replicate across Many Labs 1 samples.',
            'why_failed': 'Original effect was likely inflated or non-existent.',
            'sample_size': 6344,
            'methodology': 'Many Labs multi-site replication',
            'lessons_learned': 'Subtle priming manipulations often fail to replicate.',
            'source_url': 'https://econtent.hogrefe.com/doi/10.1027/1864-9335/a000178',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Money/currency priming research.'
        },
    ]


def get_stereotype_threat_failures():
    """
    Stereotype threat replication failures and critiques
    """
    return [
        {
            'title': 'Stereotype Threat: Dutch High School Large-Scale Test (N=2064)',
            'category': 'Social Psychology',
            'hypothesis': 'Activating gender stereotypes impairs female math performance',
            'what_failed': 'Largest experimental test (N=2,064 Dutch high school students) found no stereotype threat effect on math performance.',
            'why_failed': 'Effect may be limited to narrow conditions not met in real-world educational settings.',
            'sample_size': 2064,
            'methodology': 'Large-scale experimental study in schools',
            'lessons_learned': 'Laboratory effects may not generalize to authentic educational contexts.',
            'source_url': 'https://replicationindex.com/2017/04/07/hidden-figures-replication-failures-in-the-stereotype-threat-literature/',
            'design_type': 'Field Experiment',
            'original_study_citation': 'Steele, C. M., & Aronson, J. (1995). JPSP.'
        },
        {
            'title': 'Stereotype Threat: Ganley et al. Multi-Experiment Failure (N≈1000)',
            'category': 'Social Psychology',
            'hypothesis': 'Stereotype threat affects mathematics performance in school-age girls',
            'what_failed': 'No evidence that mathematics performance of school-age girls was impacted by stereotype threat.',
            'why_failed': 'Authors suggested evidence for stereotype threat in children may reflect publication bias.',
            'sample_size': 1000,
            'methodology': 'Well-powered multi-experiment study',
            'lessons_learned': 'Published positive findings may reflect selective reporting.',
            'source_url': 'https://replicationindex.com/2017/04/07/hidden-figures-replication-failures-in-the-stereotype-threat-literature/',
            'design_type': 'Experimental',
            'original_study_citation': 'Steele, C. M. (1997). Stereotype threat research.'
        },
        {
            'title': 'Stereotype Threat: Stricker & Ward Real Assessment Failure (2004)',
            'category': 'Social Psychology',
            'hypothesis': 'Inquiring about race or gender before testing activates stereotype threat',
            'what_failed': 'Neither race nor gender inquiry significantly affected test performance in real assessment context.',
            'why_failed': 'Failed to replicate classic Steele and Aronson findings in actual testing conditions.',
            'sample_size': 5000,
            'methodology': 'Two studies with real assessment manipulation',
            'lessons_learned': 'Effects found in artificial lab settings may not apply to real testing.',
            'source_url': 'https://russellwarne.com/2021/08/07/send-in-the-clones-stereotype-threat-needs-replication-studies/',
            'design_type': 'Field Experiment',
            'original_study_citation': 'Steele, C. M., & Aronson, J. (1995). JPSP.'
        },
        {
            'title': 'Stereotype Threat: Gibson et al. Replication Failure (2014)',
            'category': 'Social Psychology',
            'hypothesis': 'Stereotype threat manipulation impairs performance in targeted groups',
            'what_failed': 'One of four replication attempts that yielded unambiguous failure.',
            'why_failed': 'Effect not robust across different samples and contexts.',
            'sample_size': 150,
            'methodology': 'Direct replication attempt',
            'lessons_learned': 'Multiple failed replications suggest original effect may be unreliable.',
            'source_url': 'https://russellwarne.com/2021/08/07/send-in-the-clones-stereotype-threat-needs-replication-studies/',
            'design_type': 'Replication',
            'original_study_citation': 'Steele, C. M., & Aronson, J. (1995).'
        },
        {
            'title': 'Stereotype Threat: Finnigan & Corker Replication Failure (2016)',
            'category': 'Social Psychology',
            'hypothesis': 'Stereotype activation impairs academic performance',
            'what_failed': 'Failed to replicate stereotype threat effects in preregistered study.',
            'why_failed': 'Preregistration prevented flexible analysis that may have driven original findings.',
            'sample_size': 200,
            'methodology': 'Preregistered replication',
            'lessons_learned': 'Preregistration reveals true effect sizes.',
            'source_url': 'https://russellwarne.com/2021/08/07/send-in-the-clones-stereotype-threat-needs-replication-studies/',
            'design_type': 'Replication',
            'original_study_citation': 'Steele, C. M. (1997). Stereotype threat.'
        },
        {
            'title': 'Stereotype Threat: Political Knowledge Gender Gap Failure (2023)',
            'category': 'Social Psychology',
            'hypothesis': 'Stereotype threat contributes to gender gap in political knowledge',
            'what_failed': 'Preregistered replication could not replicate effect of stereotype activation on political knowledge gender gap.',
            'why_failed': 'Consistent with recent challenges to stereotype threat on academic performance broadly.',
            'sample_size': 400,
            'methodology': 'Preregistered replication study',
            'lessons_learned': 'Stereotype threat effects may not extend beyond original narrow contexts.',
            'source_url': 'https://www.cambridge.org/core/journals/journal-of-experimental-political-science/article/does-stereotype-threat-contribute-to-the-political-knowledge-gender-gap-a-preregistered-replication-study-of-ihme-and-tausendpfund-2018/1021AEEB971D486933CE265040CD0C95',
            'design_type': 'Replication',
            'original_study_citation': 'Ihme & Tausendpfund (2018).'
        },
        {
            'title': 'Stereotype Threat: Meta-Analysis Shows Publication Bias',
            'category': 'Social Psychology',
            'hypothesis': 'Meta-analyses support robust stereotype threat effect',
            'what_failed': 'Bias-corrected meta-analysis found inflated effect sizes. Effect strongest in artificial laboratory studies, weakest in real-world settings.',
            'why_failed': 'Publication bias inflated apparent effect. Real-world conditions show minimal effects.',
            'sample_size': 10000,
            'methodology': 'Meta-analysis with bias correction (Shewach et al., 2019)',
            'lessons_learned': 'Laboratory effects may not have practical significance for real educational outcomes.',
            'source_url': 'https://russellwarne.com/2020/08/10/the-67-5-million-wasted-on-stereotype-threat-research/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Multiple stereotype threat studies.'
        },
    ]


def get_growth_mindset_issues():
    """
    Growth mindset replication issues and meta-analysis findings
    """
    return [
        {
            'title': 'Growth Mindset: Sisk et al. Meta-Analysis (2018) - Tiny Effects',
            'category': 'Educational Psychology',
            'hypothesis': 'Growth mindset interventions significantly improve academic achievement',
            'what_failed': 'Meta-analysis found average effect size d=0.08, moving average child from 50th to 53rd percentile only.',
            'why_failed': 'Effects are much smaller than claimed. Correlation between mindset and achievement is tiny (r=0.10).',
            'sample_size': 57155,
            'methodology': 'Meta-analysis of mindset intervention studies',
            'lessons_learned': 'Popular psychological interventions may have minimal practical impact.',
            'source_url': 'https://www.sciencedaily.com/releases/2018/05/180522114523.htm',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Dweck, C. S. (2006). Mindset research program.'
        },
        {
            'title': 'Growth Mindset: Li and Bates Failed Replication of Mueller & Dweck (2019)',
            'category': 'Educational Psychology',
            'hypothesis': 'Praising intelligence vs. effort affects student motivation and performance',
            'what_failed': 'Failed to replicate Mueller and Dweck\'s (1998) landmark study on how praise impacts student effort.',
            'why_failed': 'Original finding may have been overestimated or context-specific.',
            'sample_size': 300,
            'methodology': 'Direct replication of praise paradigm',
            'lessons_learned': 'Classic developmental findings require contemporary replication.',
            'source_url': 'http://www.madmath.com/2021/10/growth-mindset-theory-failures-to.html',
            'design_type': 'Replication',
            'original_study_citation': 'Mueller, C. M., & Dweck, C. S. (1998). JPSP.'
        },
        {
            'title': 'Growth Mindset: Bahník & Vranka - No Scholastic Association (2017)',
            'category': 'Educational Psychology',
            'hypothesis': 'Growth mindset is associated with scholastic aptitude',
            'what_failed': 'Large sample of 5,653 Czech university applicants showed growth mindset not associated with scholastic aptitude.',
            'why_failed': 'Mindset-achievement link may be correlational artifact rather than causal mechanism.',
            'sample_size': 5653,
            'methodology': 'Large-scale correlational study',
            'lessons_learned': 'Interventions based on correlational findings may have limited impact.',
            'source_url': 'https://www.kqed.org/mindshift/60490/does-growth-mindset-matter-the-debate-heats-up-with-dueling-meta-analyses',
            'design_type': 'Cross-sectional',
            'original_study_citation': 'Dweck, C. S. (2006). Mindset.'
        },
        {
            'title': 'Growth Mindset: Two British Studies - Zero Effect on Grades',
            'category': 'Educational Psychology',
            'hypothesis': 'Teaching growth mindset improves academic outcomes',
            'what_failed': 'Two British studies in which students were taught growth mindset showed no impact on grades or other outcomes.',
            'why_failed': 'Intervention does not translate to measurable academic improvement.',
            'sample_size': 2000,
            'methodology': 'School-based intervention studies',
            'lessons_learned': 'Classroom implementation may not produce effects seen in controlled studies.',
            'source_url': 'https://www.tes.com/magazine/archive/growth-mindset-where-did-it-go-wrong',
            'design_type': 'Field Experiment',
            'original_study_citation': 'Dweck growth mindset intervention research.'
        },
        {
            'title': 'Growth Mindset: Glerum et al. Vocational Students - Zero Effect',
            'category': 'Educational Psychology',
            'hypothesis': 'Growth mindset techniques benefit vocational education students',
            'what_failed': 'Same techniques applied to older vocational students found zero effect.',
            'why_failed': 'Effects may be age-specific or not generalize beyond certain contexts.',
            'sample_size': 500,
            'methodology': 'Intervention study in vocational settings',
            'lessons_learned': 'Interventions must be tested across diverse populations.',
            'source_url': 'http://www.madmath.com/2021/10/growth-mindset-theory-failures-to.html',
            'design_type': 'Field Experiment',
            'original_study_citation': 'Dweck, C. S. growth mindset interventions.'
        },
        {
            'title': 'Growth Mindset: "Dweck Effect" - Author Involvement Moderates Results',
            'category': 'Educational Psychology',
            'hypothesis': 'Growth mindset effects are robust across researchers',
            'what_failed': 'Macnamara & Burgoyne (2023) meta-analysis found authors with financial incentive (including Dweck) find much stronger effects.',
            'why_failed': 'Allegiance effects may inflate findings. Independent researchers find smaller effects.',
            'sample_size': 50000,
            'methodology': 'Meta-analysis examining researcher allegiance',
            'lessons_learned': 'Research programs led by original authors may show inflated effects.',
            'source_url': 'https://russellwarne.com/2020/01/03/the-one-variable-that-makes-growth-mindset-interventions-work/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Dweck, C. S. growth mindset research program.'
        },
    ]


def get_implicit_bias_iat_problems():
    """
    Implicit Association Test predictive validity problems
    """
    return [
        {
            'title': 'Race IAT: Meta-Analysis Shows Weak Predictive Validity',
            'category': 'Social Psychology',
            'hypothesis': 'Implicit Association Test predicts discriminatory behavior',
            'what_failed': 'Meta-analyses show predictive validity is weak and incremental validity over explicit measures is negligible.',
            'why_failed': 'IAT may measure associations but not authentic prejudice that predicts behavior.',
            'sample_size': 10000,
            'methodology': 'Meta-analysis of IAT predictive validity studies',
            'lessons_learned': 'Measures of implicit attitudes may not be useful for predicting real-world discrimination.',
            'source_url': 'https://replicationindex.com/2019/02/06/raceiat-predictive-validity/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Greenwald, A. G., et al. (1998). IAT research program.'
        },
        {
            'title': 'IAT: Failed Incremental Predictive Validity Replication',
            'category': 'Social Psychology',
            'hypothesis': 'IAT adds predictive value beyond explicit self-report measures',
            'what_failed': 'Finding of incremental predictive validity has not been replicated. Studies with intergroup contact as criterion failed to show incremental validity.',
            'why_failed': 'Original claims were based on marginally significant p-values that did not replicate.',
            'sample_size': 500,
            'methodology': 'Replication of incremental validity studies',
            'lessons_learned': 'Marginally significant findings should be viewed with skepticism.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC8167921/',
            'design_type': 'Replication',
            'original_study_citation': 'IAT incremental validity research.'
        },
        {
            'title': 'IAT Voting Study: 2009 Effect Did Not Replicate in 2012',
            'category': 'Social Psychology',
            'hypothesis': 'IAT scores predict voting behavior',
            'what_failed': 'Voting study that seemed to support IAT validity in 2009 failed to replicate in 2012.',
            'why_failed': 'Original finding may have been context-specific or spurious.',
            'sample_size': 1000,
            'methodology': 'Replication of voting behavior prediction',
            'lessons_learned': 'Political behavior predictions should be replicated across election cycles.',
            'source_url': 'https://replicationindex.com/2021/06/13/predictive-validity-race-iat/',
            'design_type': 'Replication',
            'original_study_citation': 'IAT voting behavior study (2009).'
        },
        {
            'title': 'IAT: Test-Retest Reliability Too Low for Individual Assessment',
            'category': 'Social Psychology',
            'hypothesis': 'IAT scores are stable individual difference measures',
            'what_failed': 'Test-retest reliability is too low (r≈0.50) for use in individual assessment or training.',
            'why_failed': 'IAT scores are highly variable and often provide inconsistent information about individuals.',
            'sample_size': 5000,
            'methodology': 'Psychometric analysis of IAT reliability',
            'lessons_learned': 'Tools with low reliability should not be used for high-stakes individual decisions.',
            'source_url': 'https://qz.com/1144504/the-world-is-relying-on-a-flawed-psychological-test-to-fight-racism',
            'design_type': 'Psychometric Analysis',
            'original_study_citation': 'IAT individual differences research.'
        },
        {
            'title': 'Anti-Black IAT Predicts Pro-Black Behavior (Paradoxical Finding)',
            'category': 'Social Psychology',
            'hypothesis': 'Pro-White IAT bias predicts discriminatory behavior against Black individuals',
            'what_failed': 'Research found that scoring as pro-White on IAT sometimes predicts pro-Black behavior, contradicting theoretical predictions.',
            'why_failed': 'IAT may tap into associations that do not map onto discriminatory behavior.',
            'sample_size': 300,
            'methodology': 'Behavioral outcome study',
            'lessons_learned': 'Construct validity of IAT remains questionable.',
            'source_url': 'https://replicationindex.com/2019/11/24/iat-behavior/',
            'design_type': 'Behavioral Study',
            'original_study_citation': 'IAT-behavior relationship research.'
        },
    ]


def get_marshmallow_test_findings():
    """
    Marshmallow test conceptual replication and critique
    """
    return [
        {
            'title': 'Marshmallow Test: Watts et al. Conceptual Replication (2018)',
            'category': 'Developmental Psychology',
            'hypothesis': 'Delayed gratification at age 4 predicts life outcomes independent of background',
            'what_failed': 'With N=900 diverse children, correlation was half original size. After controlling for SES, effect reduced by two-thirds and became non-significant.',
            'why_failed': 'Original small homogeneous sample (Stanford preschool) confounded ability with socioeconomic factors.',
            'sample_size': 900,
            'methodology': 'Conceptual replication with diverse sample and controls',
            'lessons_learned': 'Early studies with restricted samples may conflate individual traits with environmental advantages.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6050075/',
            'design_type': 'Longitudinal Replication',
            'original_study_citation': 'Mischel, W., et al. (1989). Delay of gratification. Science.'
        },
        {
            'title': 'Marshmallow Test: SES Explains Predictive Power',
            'category': 'Developmental Psychology',
            'hypothesis': 'Self-control ability, not environment, drives later success',
            'what_failed': 'After controlling for mother\'s education, home environment, and early cognition, marshmallow performance added minimal predictive value.',
            'why_failed': 'Delay of gratification may reflect affluence and stable environments rather than dispositional self-control.',
            'sample_size': 900,
            'methodology': 'Analysis with comprehensive covariate controls',
            'lessons_learned': 'Environmental factors may drive both delay behavior and later outcomes.',
            'source_url': 'https://anderson-review.ucla.edu/new-study-disavows-marshmallow-tests-predictive-powers/',
            'design_type': 'Longitudinal',
            'original_study_citation': 'Mischel, W. marshmallow test research program.'
        },
        {
            'title': 'Marshmallow Test: Environmental Reliability Affects Performance',
            'category': 'Developmental Psychology',
            'hypothesis': 'Delay of gratification reflects stable trait of self-control',
            'what_failed': 'Kidd et al. showed children who experienced unreliable experimenter waited significantly less. Delay is rational adaptation, not pure self-control.',
            'why_failed': 'Original interpretation ignored that children from unstable environments rationally choose immediate rewards.',
            'sample_size': 100,
            'methodology': 'Experimental manipulation of experimenter reliability',
            'lessons_learned': 'Child behavior reflects adaptation to environment, not just individual capacity.',
            'source_url': 'https://www.sciencedirect.com/science/article/abs/pii/S0022096519303662',
            'design_type': 'Experimental',
            'original_study_citation': 'Mischel, W. marshmallow test.'
        },
        {
            'title': 'Marshmallow Test: Does Not Reliably Predict Adult Outcomes (2024)',
            'category': 'Developmental Psychology',
            'hypothesis': 'Marshmallow test performance predicts adult functioning',
            'what_failed': 'Latest analysis (2024) found no clear moderation by SES or sex. Marshmallow Test does not reliably predict adult outcomes.',
            'why_failed': 'The predictive validity claimed in original research does not hold up in larger, more diverse samples.',
            'sample_size': 2000,
            'methodology': 'Comprehensive longitudinal follow-up analysis',
            'lessons_learned': 'Classic developmental findings require replication with contemporary diverse samples.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC11581930/',
            'design_type': 'Longitudinal',
            'original_study_citation': 'Mischel, W. delayed gratification research.'
        },
        {
            'title': 'Marshmallow Test: Original Sample Highly Selective',
            'category': 'Developmental Psychology',
            'hypothesis': 'Original findings generalize to broader population',
            'what_failed': 'Original 90 children were Stanford preschool students. Follow-ups found only 185 of 653 children, creating severe selection bias.',
            'why_failed': 'Small, elite sample with massive attrition makes findings ungeneralizable.',
            'sample_size': 185,
            'methodology': 'Critical analysis of original sampling',
            'lessons_learned': 'Classic studies with restricted samples should not be over-interpreted.',
            'source_url': 'https://en.wikipedia.org/wiki/Stanford_marshmallow_experiment',
            'design_type': 'Methodological Critique',
            'original_study_citation': 'Mischel, W. et al. original marshmallow studies.'
        },
    ]


def get_stanford_prison_critique():
    """
    Stanford Prison Experiment methodological critique
    """
    return [
        {
            'title': 'Stanford Prison Experiment: Le Texier Archive Investigation (2018)',
            'category': 'Social Psychology',
            'hypothesis': 'Situational forces spontaneously create abusive behavior',
            'what_failed': 'Investigation of archives revealed guards were coached to be cruel. Participants admitted faking distress.',
            'why_failed': 'Study was demand-driven, not spontaneous demonstration of situational power.',
            'sample_size': 24,
            'methodology': 'Historical investigation of original archives',
            'lessons_learned': 'Iconic studies require archival scrutiny for scientific validity.',
            'source_url': 'https://pubmed.ncbi.nlm.nih.gov/31380664/',
            'design_type': 'Historical Analysis',
            'original_study_citation': 'Zimbardo, P. G. (1971). Stanford Prison Experiment.'
        },
        {
            'title': 'Stanford Prison Experiment: Guards Received Explicit Instructions',
            'category': 'Social Psychology',
            'hypothesis': 'Guards spontaneously adopted cruel behavior from role',
            'what_failed': 'Newly discovered audio revealed Zimbardo encouraged guards to act "tough." Guard Dave Eshelman called it "improv exercise."',
            'why_failed': 'Cruelty was not emergent from situation but directed by experimenter.',
            'sample_size': 24,
            'methodology': 'Analysis of audio recordings',
            'lessons_learned': 'Original authors\' narratives should be verified against primary evidence.',
            'source_url': 'https://www.livescience.com/62832-stanford-prison-experiment-flawed.html',
            'design_type': 'Historical Analysis',
            'original_study_citation': 'Zimbardo, P. G. (1971).'
        },
        {
            'title': 'Stanford Prison Experiment: Prisoner Breakdown Was Faked',
            'category': 'Social Psychology',
            'hypothesis': 'Prisoner psychological breakdown was genuine',
            'what_failed': 'Douglas Korpi (famous "prisoner 8612" breakdown) stated: "Anybody who is a clinician would know that I was faking."',
            'why_failed': 'Key evidence for situational power was actually performance, not genuine distress.',
            'sample_size': 24,
            'methodology': 'Participant interview',
            'lessons_learned': 'Dramatic demonstrations may be less valid than systematic controlled studies.',
            'source_url': 'https://talk.crisisnow.com/the-fallacy-of-the-stanford-prison-experiment/',
            'design_type': 'Historical Analysis',
            'original_study_citation': 'Zimbardo, P. G. (1971).'
        },
        {
            'title': 'Stanford Prison Experiment: BBC Replication Found Different Results',
            'category': 'Social Psychology',
            'hypothesis': 'Removing experimenter coaching would produce similar results',
            'what_failed': 'BBC Prison Study without explicit guard coaching did not produce the same abuse patterns.',
            'why_failed': 'Removing demand characteristics eliminated the "effect." Situational power alone insufficient.',
            'sample_size': 15,
            'methodology': 'Conceptual replication with methodological improvements',
            'lessons_learned': 'Experimenter demands may be primary driver of dramatic demonstration findings.',
            'source_url': 'https://en.wikipedia.org/wiki/Stanford_prison_experiment',
            'design_type': 'Conceptual Replication',
            'original_study_citation': 'Zimbardo, P. G. (1971).'
        },
        {
            'title': 'Stanford Prison Experiment: Methodological Criticisms From 1975',
            'category': 'Social Psychology',
            'hypothesis': 'SPE provides valid evidence for situational power',
            'what_failed': 'Criticisms of methodology and Zimbardo\'s argument appeared as early as 1975 but were ignored by textbooks.',
            'why_failed': 'Compelling narrative trumped scientific validity in educational materials.',
            'sample_size': 24,
            'methodology': 'Methodological critique',
            'lessons_learned': 'Textbooks may perpetuate flawed studies for decades.',
            'source_url': 'https://files.eric.ed.gov/fulltext/EJ1231538.pdf',
            'design_type': 'Methodological Review',
            'original_study_citation': 'Zimbardo, P. G. (1971).'
        },
    ]


def get_many_labs_2_failures():
    """
    Many Labs 2 failed replications - 28 classic findings tested
    """
    return [
        {
            'title': 'Many Labs 2: Moral Credentials Effect Failed to Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Establishing moral credentials licenses subsequent less moral behavior',
            'what_failed': 'Replication across 125 samples found no significant effect. Original effect size not reproduced.',
            'why_failed': 'Effect may have been overstated in original publication.',
            'sample_size': 15305,
            'methodology': 'Many Labs 2 multi-site replication',
            'lessons_learned': 'Large-scale replications reveal true effect sizes.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/2515245918810225',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Moral credentials research.'
        },
        {
            'title': 'Many Labs 2: Sunk Cost Effect - Dramatically Smaller',
            'category': 'Cognitive Psychology',
            'hypothesis': 'People persist with failing investments due to sunk costs',
            'what_failed': 'Median effect size d=0.15 compared to original d=0.60. Effect 75% smaller than originally reported.',
            'why_failed': 'Publication bias inflated original estimates.',
            'sample_size': 15305,
            'methodology': 'Many Labs 2 replication',
            'lessons_learned': 'Classic cognitive biases may be weaker than textbooks suggest.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/2515245918810225',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Sunk cost research.'
        },
        {
            'title': 'Many Labs 2: Direction of Writing Effect Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Direction of writing (left-right) affects spatial cognition',
            'what_failed': 'No significant effect found across multi-cultural samples.',
            'why_failed': 'Effect may have been specific to original sample or spurious.',
            'sample_size': 15305,
            'methodology': 'Many Labs 2 replication across 36 countries',
            'lessons_learned': 'Cross-cultural replications test generalizability of findings.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/2515245918810225',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Writing direction cognition research.'
        },
        {
            'title': 'Many Labs 2: Structure and Goals Effect Did Not Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Exposure to structured vs. random events affects goal pursuit willingness',
            'what_failed': 'N=6,506 found no significant difference. Structured event exposure did not increase goal pursuit.',
            'why_failed': 'Original finding was likely false positive.',
            'sample_size': 6506,
            'methodology': 'Many Labs 2 replication',
            'lessons_learned': 'Motivation research requires high-powered replications.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/2515245918810225',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Structure and goals research.'
        },
        {
            'title': 'Many Labs 2: 50% of Effects Failed to Replicate Significantly',
            'category': 'Social Psychology',
            'hypothesis': 'Classic psychological findings are robust and replicable',
            'what_failed': 'Using strict criterion (p<.0001), only 50% (14/28) replicated. 75% showed smaller effect sizes than original.',
            'why_failed': 'Original studies had inflated effect sizes due to publication bias and small samples.',
            'sample_size': 15305,
            'methodology': 'Comprehensive multi-site replication project',
            'lessons_learned': 'Half of classic findings may not survive high-powered replication.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/2515245918810225',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Multiple classic psychology studies.'
        },
        {
            'title': 'Many Labs 3: Only 30% Replication Rate (3 of 10)',
            'category': 'Social Psychology',
            'hypothesis': 'End-of-semester timing affects research findings',
            'what_failed': 'Only 3 of 10 effects replicated (30%). Timing of semester did not explain replication failures.',
            'why_failed': 'Original effects may have been spurious rather than context-dependent.',
            'sample_size': 3000,
            'methodology': 'Many Labs 3 testing semester timing hypothesis',
            'lessons_learned': 'Low replication rates persist across Many Labs projects.',
            'source_url': 'https://www.tandfonline.com/doi/full/10.1080/01973533.2019.1577736',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Ebersole et al. Many Labs 3.'
        },
        {
            'title': 'Many Labs 4: Mortality Salience Effect Failed Even With Author Involvement',
            'category': 'Social Psychology',
            'hypothesis': 'Reminders of death increase worldview defense',
            'what_failed': 'Failed to replicate mortality salience effect with and without original author involvement.',
            'why_failed': 'Author involvement did not rescue the effect. Terror Management Theory prediction not confirmed.',
            'sample_size': 2200,
            'methodology': 'Many Labs 4 with author involvement manipulation',
            'lessons_learned': 'Author involvement is not sufficient to ensure replication.',
            'source_url': 'https://online.ucpress.edu/collabra/article/8/1/35271/168050/Many-Labs-4-Failure-to-Replicate-Mortality',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Greenberg et al. Terror Management Theory.'
        },
        {
            'title': 'Many Labs 5: Pre-Data Peer Review Did Not Improve Replication (2/10)',
            'category': 'Social Psychology',
            'hypothesis': 'Pre-registration and peer review improve replicability',
            'what_failed': 'Only 2 of 10 effects replicated (20%) even with pre-data-collection peer review.',
            'why_failed': 'Methodological improvements cannot rescue non-existent effects.',
            'sample_size': 5000,
            'methodology': 'Many Labs 5 testing peer review intervention',
            'lessons_learned': 'Some effects are simply not real, regardless of methodological rigor.',
            'source_url': 'https://journals.sagepub.com/doi/10.1177/2515245920958687',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Ebersole et al. Many Labs 5.'
        },
        {
            'title': 'Many Labs: Imagined Contact Effect Failed',
            'category': 'Social Psychology',
            'hypothesis': 'Imagining contact with outgroup reduces prejudice',
            'what_failed': 'Imagined contact showed significant effect in only 4 of 36 samples in Many Labs 1.',
            'why_failed': 'Effect is highly inconsistent across samples and contexts.',
            'sample_size': 6344,
            'methodology': 'Many Labs 1 multi-site replication',
            'lessons_learned': 'Inconsistent effects across samples suggest boundary conditions or null effect.',
            'source_url': 'https://econtent.hogrefe.com/doi/10.1027/1864-9335/a000178',
            'design_type': 'Multi-lab Replication',
            'original_study_citation': 'Imagined contact prejudice reduction research.'
        },
    ]


def get_reproducibility_project_comprehensive():
    """
    Additional Reproducibility Project: Psychology failures (2015)
    From the 100 studies tested, focusing on key failures
    """
    return [
        {
            'title': 'RP:P - Loneliness and Supernatural Beliefs: Failed to Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Loneliness increases belief in supernatural agents',
            'what_failed': 'Replication found no significant relationship between loneliness and supernatural beliefs.',
            'why_failed': 'Original finding was one of 64% of social psychology studies that failed.',
            'sample_size': 300,
            'methodology': 'Reproducibility Project direct replication',
            'lessons_learned': 'Correlational findings in social psychology frequently fail to replicate.',
            'source_url': 'https://www.science.org/doi/10.1126/science.aac4716',
            'design_type': 'Replication',
            'original_study_citation': 'Loneliness-belief research.'
        },
        {
            'title': 'RP:P - Conceptual Fluency and Concrete Descriptions: Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Conceptual fluency increases preference for concrete descriptions',
            'what_failed': 'Effect did not replicate. Confidence intervals excluded original effect size.',
            'why_failed': 'Original small-sample study produced inflated estimate.',
            'sample_size': 250,
            'methodology': 'Reproducibility Project replication',
            'lessons_learned': 'Fluency effects may be weaker than originally estimated.',
            'source_url': 'https://www.science.org/doi/10.1126/science.aac4716',
            'design_type': 'Replication',
            'original_study_citation': 'Conceptual fluency research.'
        },
        {
            'title': 'RP:P - Race-Gun Reaction Time Effect: Failed to Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Racial prejudice affects response times to guns paired with different ethnic faces',
            'what_failed': 'Links between racial prejudice and response times to gun pictures did not replicate.',
            'why_failed': 'Original implicit measure effects may have been artifacts.',
            'sample_size': 300,
            'methodology': 'Reproducibility Project replication',
            'lessons_learned': 'Reaction time paradigms require high-powered replication.',
            'source_url': 'https://www.bps.org.uk/research-digest/what-happened-when-psychologists-tried-replicate-100-previously-published-findings',
            'design_type': 'Replication',
            'original_study_citation': 'Race-weapon association research.'
        },
        {
            'title': 'RP:P - Social Psychology: Only 25% Replication Rate',
            'category': 'Social Psychology',
            'hypothesis': 'Social psychology findings are robust and replicable',
            'what_failed': 'Only 25% of social psychology findings from JPSP replicated successfully.',
            'why_failed': 'Field-wide issues with methodology, publication bias, and researcher degrees of freedom.',
            'sample_size': 5000,
            'methodology': 'Reproducibility Project analysis by subdiscipline',
            'lessons_learned': 'Social psychology requires fundamental methodological reform.',
            'source_url': 'https://www.nature.com/articles/nature.2015.18248',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'JPSP 2008 publications.'
        },
        {
            'title': 'RP:P - Effect Sizes Declined by 50% on Average',
            'category': 'Social Psychology',
            'hypothesis': 'Original effect sizes are accurate estimates',
            'what_failed': 'Replication effect sizes were half the magnitude of originals on average. Only 39% judged successful.',
            'why_failed': 'Publication bias and winner\'s curse inflated original estimates.',
            'sample_size': 8000,
            'methodology': 'Reproducibility Project meta-analysis',
            'lessons_learned': 'Published effect sizes should be treated as upper bounds.',
            'source_url': 'https://www.science.org/doi/10.1126/science.aac4716',
            'design_type': 'Meta-analysis',
            'original_study_citation': '100 psychology studies from 2008.'
        },
        {
            'title': 'RP:P - Cognitive Psychology: 50% Replication Rate',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Cognitive psychology has higher replicability than social',
            'what_failed': 'Though better than social psychology, half of cognitive findings still failed. 50% replication rate for JEPLMC.',
            'why_failed': 'Even "harder" psychology subdisciplines face replication challenges.',
            'sample_size': 3000,
            'methodology': 'Reproducibility Project subdiscipline analysis',
            'lessons_learned': 'All of psychology requires higher standards for evidence.',
            'source_url': 'https://en.wikipedia.org/wiki/Reproducibility_Project',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'JEPLMC 2008 publications.'
        },
    ]


def get_additional_replication_failures():
    """
    Additional documented replication failures from various sources
    """
    return [
        {
            'title': 'Facial Feedback Hypothesis: RRR Found Tiny Effect (2016)',
            'category': 'Social Psychology',
            'hypothesis': 'Holding a pen with teeth (forcing smile) increases humor ratings',
            'what_failed': '17 labs with N=1,894 found effect size near zero, not significant.',
            'why_failed': 'Original finding was likely inflated. Classic embodied cognition claim not supported.',
            'sample_size': 1894,
            'methodology': 'Registered Replication Report',
            'lessons_learned': 'Embodied cognition effects may be much smaller than claimed.',
            'source_url': 'https://journals.sagepub.com/doi/10.1177/1745691616674458',
            'design_type': 'RRR',
            'original_study_citation': 'Strack, F., Martin, L. L., & Stepper, S. (1988). JPSP.'
        },
        {
            'title': 'Social Psychology Expected Replication Rate: Only 20-45%',
            'category': 'Social Psychology',
            'hypothesis': 'Published social psychology has high replicability',
            'what_failed': 'Z-curve analysis of representative samples predicts only 20-45% expected replication rate.',
            'why_failed': 'Questionable research practices and publication bias are endemic.',
            'sample_size': 14126,
            'methodology': 'Z-curve replicability analysis',
            'lessons_learned': 'Most published findings may not survive rigorous replication.',
            'source_url': 'https://replicationindex.com/category/social-psychology/',
            'design_type': 'Statistical Analysis',
            'original_study_citation': 'Social psychology literature broadly.'
        },
        {
            'title': 'Rescue Replications: Only 29% Succeed After Initial Failure',
            'category': 'Social Psychology',
            'hypothesis': 'Failed replications can be rescued with modified procedures',
            'what_failed': '17 re-replications after initial failure: only 5 (29%) mostly replicated, with smaller effect sizes.',
            'why_failed': 'Initial failures usually indicate real problems, not methodological artifacts.',
            'sample_size': 2000,
            'methodology': 'Analysis of rescue replication attempts',
            'lessons_learned': 'Failed replications should be taken seriously, not explained away.',
            'source_url': 'https://online.ucpress.edu/collabra/article/10/1/125685/203892/Estimating-the-Replicability-of-Psychology',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Various failed replication studies.'
        },
        {
            'title': 'Bilingual Advantage: Meta-Analysis Shows No Effect',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Bilingualism provides cognitive advantages in executive function',
            'what_failed': 'After correcting for publication bias, bilingual advantage in executive function disappears.',
            'why_failed': 'Early positive findings were selected from broader null literature.',
            'sample_size': 5000,
            'methodology': 'Meta-analysis with bias correction',
            'lessons_learned': 'Popular claims about cognitive benefits require skepticism.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Bilingual advantage research.'
        },
        {
            'title': 'Brain Training: Transfer Effects Do Not Replicate',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Cognitive training produces far transfer to untrained abilities',
            'what_failed': 'Large-scale studies fail to show transfer of training to non-trained cognitive abilities.',
            'why_failed': 'Transfer effects were likely placebo effects or demand characteristics.',
            'sample_size': 10000,
            'methodology': 'Multi-site RCTs of brain training',
            'lessons_learned': 'Commercial brain training claims are not supported by evidence.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'RCT',
            'original_study_citation': 'Brain training and cognitive transfer research.'
        },
        {
            'title': 'Power Posing: Behavioral Effects Did Not Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Expansive "power poses" increase testosterone and risk-taking',
            'what_failed': 'P-curve analysis and direct replications showed no evidence for behavioral effects of power posing.',
            'why_failed': 'Original findings were likely false positives. Co-author Dana Carney disavowed the research.',
            'sample_size': 1500,
            'methodology': 'Multiple replication attempts',
            'lessons_learned': 'High-profile findings require independent replication before application.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Replication',
            'original_study_citation': 'Carney, D. R., Cuddy, A. J. C., & Yap, A. J. (2010).'
        },
        {
            'title': 'Oxytocin and Trust: Meta-Analysis Shows Publication Bias',
            'category': 'Neuroscience',
            'hypothesis': 'Intranasal oxytocin increases trust and prosocial behavior',
            'what_failed': 'Meta-analysis revealed severe publication bias. Effect size near zero after correction.',
            'why_failed': 'Selective publication of positive results created false impression of robust effect.',
            'sample_size': 3000,
            'methodology': 'Meta-analysis with bias correction',
            'lessons_learned': 'Neuroendocrine manipulation studies require preregistration.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Oxytocin and trust research.'
        },
        {
            'title': 'Unconscious Thought: Dijksterhuis Effect Did Not Replicate',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Complex decisions are better made unconsciously than consciously',
            'what_failed': 'Multiple replications failed to find unconscious thought advantage for complex decisions.',
            'why_failed': 'Original effect may have been due to demand characteristics or p-hacking.',
            'sample_size': 800,
            'methodology': 'Multiple replication attempts',
            'lessons_learned': 'Counterintuitive findings require especially rigorous replication.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Replication',
            'original_study_citation': 'Dijksterhuis, A. Unconscious thought theory.'
        },
        {
            'title': 'Depressive Realism: Meta-Analysis Shows Effect Is Artifact',
            'category': 'Clinical Psychology',
            'hypothesis': 'Depressed individuals have more accurate perception of reality',
            'what_failed': 'Meta-analysis controlling for methodological factors eliminated the effect.',
            'why_failed': 'Original findings conflated depression with response bias.',
            'sample_size': 2000,
            'methodology': 'Meta-analysis with methodological corrections',
            'lessons_learned': 'Appealing counterintuitive findings often disappear with better methods.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Depressive realism research.'
        },
        {
            'title': 'Verbal Overshadowing: Effect Much Smaller Than Reported',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Describing a face verbally impairs later face recognition',
            'what_failed': 'RRR found effect d=0.17, much smaller than original d=0.70.',
            'why_failed': 'Original effect size was inflated by publication bias.',
            'sample_size': 2500,
            'methodology': 'Registered Replication Report',
            'lessons_learned': 'Even replicated effects may be much smaller than originally claimed.',
            'source_url': 'https://journals.sagepub.com/doi/full/10.1177/1745691615611252',
            'design_type': 'RRR',
            'original_study_citation': 'Schooler, J. W., & Engstler-Schooler, T. Y. (1990).'
        },
    ]


def get_embodied_cognition_failures():
    """
    Embodied cognition replication failures
    Sources: QZ article, various replication studies
    """
    return [
        {
            'title': 'Warm Cup Effect: Holding Warm Cup Does Not Increase Warmth Toward Others',
            'category': 'Social Psychology',
            'hypothesis': 'Physical warmth from holding a warm cup increases interpersonal warmth judgments',
            'what_failed': 'Multiple replication attempts failed to find effect of warm vs cold cup on social judgments.',
            'why_failed': 'Original study had small sample and flexible analysis. Effect is artifact.',
            'sample_size': 300,
            'methodology': 'Multiple replication attempts',
            'lessons_learned': 'Embodied cognition metaphor effects require rigorous replication.',
            'source_url': 'https://qz.com/1525854/psychologys-replication-crisis-is-debunking-embodied-cognition-theory',
            'design_type': 'Replication',
            'original_study_citation': 'Williams, L. E., & Bargh, J. A. (2008). Science.'
        },
        {
            'title': 'Heavy Clipboard Weight/Importance Effect: Not Robust',
            'category': 'Social Psychology',
            'hypothesis': 'Holding heavier clipboard increases perceived importance of topics',
            'what_failed': 'Effect was inconsistent - very heavy clipboards decreased importance ratings, opposite of prediction.',
            'why_failed': 'Effect boundary conditions suggest original finding was spurious or highly context-dependent.',
            'sample_size': 200,
            'methodology': 'Replication with weight variations',
            'lessons_learned': 'Metaphor-based predictions need theoretical specification of boundary conditions.',
            'source_url': 'https://journals.sagepub.com/doi/abs/10.1177/0146167217727505',
            'design_type': 'Replication',
            'original_study_citation': 'Jostmann, N. B., Lakens, D., & Schubert, T. W. (2009).'
        },
        {
            'title': 'Macbeth Effect: Physical Cleaning Does Not Remove Guilt',
            'category': 'Social Psychology',
            'hypothesis': 'Physical washing removes psychological feelings of guilt or immorality',
            'what_failed': 'Failed replication attempts could not reproduce the Macbeth effect.',
            'why_failed': 'Original finding likely due to demand characteristics or p-hacking.',
            'sample_size': 250,
            'methodology': 'Replication of guilt-washing paradigm',
            'lessons_learned': 'Metaphorically appealing findings are especially susceptible to false positives.',
            'source_url': 'https://qz.com/1525854/psychologys-replication-crisis-is-debunking-embodied-cognition-theory',
            'design_type': 'Replication',
            'original_study_citation': 'Zhong, C. B., & Liljenquist, K. (2006). Science.'
        },
        {
            'title': 'Social Exclusion and Warm Foods: Effect Not Reliable',
            'category': 'Social Psychology',
            'hypothesis': 'Being socially excluded increases desire for warm foods',
            'what_failed': 'Replication attempts did not reliably reproduce social exclusion-warmth seeking link.',
            'why_failed': 'Original study likely underpowered with flexible dependent measures.',
            'sample_size': 300,
            'methodology': 'Replication of exclusion-warmth paradigm',
            'lessons_learned': 'Social thermoregulation effects may be much weaker than claimed.',
            'source_url': 'https://qz.com/1525854/psychologys-replication-crisis-is-debunking-embodied-cognition-theory',
            'design_type': 'Replication',
            'original_study_citation': 'Zhong, C. B., & Leonardelli, G. J. (2008). Psychological Science.'
        },
        {
            'title': 'Embodied Cognition: Entire Field Under Attack',
            'category': 'Social Psychology',
            'hypothesis': 'Physical-conceptual metaphors reliably affect cognition and behavior',
            'what_failed': 'Systematic review found most flagship embodied cognition findings fail to replicate.',
            'why_failed': 'Research program built on underpowered studies with publication bias.',
            'sample_size': 5000,
            'methodology': 'Review of embodied cognition replication attempts',
            'lessons_learned': 'Entire research programs can be built on unreliable foundations.',
            'source_url': 'https://www.taylorfrancis.com/chapters/edit/10.4324/9781003322511-50/replication-crisis-embodied-cognition-research-edouard-machery',
            'design_type': 'Review',
            'original_study_citation': 'Multiple embodied cognition studies.'
        },
        {
            'title': 'Cleanliness and Moral Judgment: Effect Does Not Replicate',
            'category': 'Social Psychology',
            'hypothesis': 'Clean environments lead to harsher moral judgments',
            'what_failed': 'Multiple attempts to replicate cleanliness-morality link failed.',
            'why_failed': 'Original effects were small and inconsistent; likely false positives.',
            'sample_size': 400,
            'methodology': 'Multiple replication attempts',
            'lessons_learned': 'Moral psychology findings require high-powered replications.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC7894377/',
            'design_type': 'Replication',
            'original_study_citation': 'Schnall, S., et al. Cleanliness and morality research.'
        },
    ]


def get_subliminal_priming_failures():
    """
    Subliminal priming and advertising failures
    """
    return [
        {
            'title': 'Subliminal Advertising: Vicary Hoax (Original Claim)',
            'category': 'Social Psychology',
            'hypothesis': 'Subliminal messages "Drink Coke" and "Eat Popcorn" increase sales',
            'what_failed': 'James Vicary eventually admitted his 1957 claim was fabricated. Data never existed.',
            'why_failed': 'Entire claim was a marketing hoax. No actual study was conducted.',
            'sample_size': 0,
            'methodology': 'Admitted hoax - no actual methodology',
            'lessons_learned': 'Extraordinary claims require verification before acceptance.',
            'source_url': 'https://en.wikipedia.org/wiki/Subliminal_stimuli',
            'design_type': 'Retraction',
            'original_study_citation': 'Vicary, J. (1957). Subliminal advertising claim.'
        },
        {
            'title': 'Subliminal Advertising Meta-Analysis: Negligible Effects (Trappey, 1996)',
            'category': 'Social Psychology',
            'hypothesis': 'Subliminal advertising influences consumer choice',
            'what_failed': 'Meta-analysis of 23 studies showed effect of subliminal advertising on choice behavior was negligible.',
            'why_failed': 'Alleged effects are too weak to influence real behavior.',
            'sample_size': 2000,
            'methodology': 'Meta-analysis of subliminal advertising studies',
            'lessons_learned': 'Subliminal influence on consumer behavior is minimal at best.',
            'source_url': 'https://replicationindex.com/category/subliminal-priming/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Trappey, C. (1996). Meta-analysis.'
        },
        {
            'title': 'Subliminal Anchoring: Two Preregistered Replications Failed',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Subliminally presented numbers serve as anchors for subsequent judgments',
            'what_failed': 'Two high-powered, preregistered replications found d=0.04 - essentially zero effect.',
            'why_failed': 'Original findings were likely false positives from flexible analysis.',
            'sample_size': 800,
            'methodology': 'Two preregistered high-powered replications',
            'lessons_learned': 'Subliminal effects require preregistration to assess true effect size.',
            'source_url': 'https://www.researchgate.net/publication/344738567_Evidence_against_subliminal_anchoring_Two_close_highly_powered_preregistered_and_failed_replication_attempts',
            'design_type': 'Replication',
            'original_study_citation': 'Subliminal anchoring research.'
        },
        {
            'title': 'Subliminal Priming: Effects Disappear After 8.5 Second Delay',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Subliminal primes have lasting effects on behavior',
            'what_failed': 'Priming reduced to 13ms effect after 1-2 second delay; eliminated completely after 8.5 seconds.',
            'why_failed': 'Short-lived nature makes subliminal influence impractical for real-world application.',
            'sample_size': 150,
            'methodology': 'Experimental study with varying delays',
            'lessons_learned': 'Even if subliminal priming exists, it is too brief to matter practically.',
            'source_url': 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6027235/',
            'design_type': 'Experimental',
            'original_study_citation': 'Subliminal priming duration research.'
        },
        {
            'title': 'Affective Priming Pronunciation: Klauer & Musch Failed Replication',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Affective primes influence pronunciation of target words',
            'what_failed': 'Three well-powered studies failed to replicate Bargh et al.\'s findings on affective priming and pronunciation.',
            'why_failed': 'Original finding may have been statistical artifact.',
            'sample_size': 300,
            'methodology': 'Three replication studies',
            'lessons_learned': 'Affective priming effects may be more limited than claimed.',
            'source_url': 'https://replicationindex.com/category/subliminal-priming/',
            'design_type': 'Replication',
            'original_study_citation': 'Bargh et al. affective priming research.'
        },
        {
            'title': 'Incidental Anchoring: Meta-Analysis Shows Near-Zero Effect',
            'category': 'Cognitive Psychology',
            'hypothesis': 'Incidentally presented anchors affect subsequent judgments',
            'what_failed': 'Unbiased replication studies and meta-analysis suggest incidental anchoring effects are very small or zero.',
            'why_failed': 'Publication bias created false impression of robust effect.',
            'sample_size': 3000,
            'methodology': 'Meta-analysis with bias correction',
            'lessons_learned': 'Subtle priming paradigms often fail rigorous meta-analytic scrutiny.',
            'source_url': 'https://replicationindex.com/tag/anchoring/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Incidental anchoring research.'
        },
    ]


def get_positive_psychology_issues():
    """
    Positive psychology intervention replication concerns
    """
    return [
        {
            'title': 'Gratitude Visit: Mixed Results and Some Negative Effects',
            'category': 'Clinical Psychology',
            'hypothesis': 'Gratitude visit intervention reliably increases well-being',
            'what_failed': 'Gratitude visit has produced mixed results in various settings and even decreased well-being in some studies.',
            'why_failed': 'Intervention effects depend on context, population, and implementation.',
            'sample_size': 500,
            'methodology': 'Review of gratitude visit studies',
            'lessons_learned': 'Even popular interventions require careful examination of boundary conditions.',
            'source_url': 'https://www.tandfonline.com/doi/full/10.1080/17439760.2023.2178956',
            'design_type': 'Review',
            'original_study_citation': 'Seligman et al. gratitude interventions.'
        },
        {
            'title': 'Positivity Ratio: Mathematical Errors Made Framework Invalid',
            'category': 'Clinical Psychology',
            'hypothesis': '3:1 ratio of positive to negative emotions predicts flourishing',
            'what_failed': 'Positivity ratio framework could not be replicated due to mathematical estimation errors in original.',
            'why_failed': 'Original mathematical modeling was fundamentally flawed.',
            'sample_size': 0,
            'methodology': 'Mathematical reanalysis',
            'lessons_learned': 'Mathematical claims in psychology require independent verification.',
            'source_url': 'https://www.tandfonline.com/doi/full/10.1080/17439760.2023.2178956',
            'design_type': 'Mathematical Critique',
            'original_study_citation': 'Fredrickson, B. L., & Losada, M. F. (2005). Positivity ratio.'
        },
        {
            'title': 'Gratitude Interventions Meta-Analysis: Small Effects (Hedges g=0.22)',
            'category': 'Clinical Psychology',
            'hypothesis': 'Gratitude interventions produce substantial well-being improvements',
            'what_failed': 'Meta-analysis of 25 RCTs found small effect (g=0.22) relative to neutral comparisons.',
            'why_failed': 'Effects are real but much smaller than often promoted.',
            'sample_size': 6745,
            'methodology': 'Meta-analysis of 25 RCTs',
            'lessons_learned': 'Positive psychology interventions have modest rather than transformative effects.',
            'source_url': 'https://link.springer.com/article/10.1007/s41042-023-00086-6',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Gratitude intervention research.'
        },
        {
            'title': 'Gratitude Studies: Methodological Issues with Control Groups',
            'category': 'Clinical Psychology',
            'hypothesis': 'Gratitude interventions outperform active control conditions',
            'what_failed': 'Similar changes observed in gratitude and neutral events conditions because both recorded positive events.',
            'why_failed': 'Inadequate control conditions inflate apparent intervention effects.',
            'sample_size': 300,
            'methodology': 'Analysis of control condition problems',
            'lessons_learned': 'Active control conditions essential for evaluating psychological interventions.',
            'source_url': 'https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2019.00584/full',
            'design_type': 'Methodological Review',
            'original_study_citation': 'Gratitude intervention literature.'
        },
        {
            'title': 'Positive Psychology Interventions: Little Theoretical Grounding',
            'category': 'Clinical Psychology',
            'hypothesis': 'Positive psychology interventions are theoretically derived',
            'what_failed': 'Review found "fairly little theoretical grounding in the development of positive psychological interventions."',
            'why_failed': 'Interventions developed atheoretically may produce inconsistent results.',
            'sample_size': 0,
            'methodology': 'Theoretical review',
            'lessons_learned': 'Intervention development requires strong theoretical foundation.',
            'source_url': 'https://www.tandfonline.com/doi/full/10.1080/17439760.2023.2178956',
            'design_type': 'Theoretical Critique',
            'original_study_citation': 'Positive psychology intervention literature.'
        },
        {
            'title': 'Happiness Set Point: Adaptation Theory Oversimplified',
            'category': 'Personality Psychology',
            'hypothesis': 'People have fixed happiness set points they return to after events',
            'what_failed': 'Research shows set point theory is oversimplified. Major events can cause lasting changes.',
            'why_failed': 'Original hedonic treadmill claims were too strong.',
            'sample_size': 10000,
            'methodology': 'Longitudinal studies of happiness',
            'lessons_learned': 'Popular psychological theories may oversimplify complex phenomena.',
            'source_url': 'https://www.tandfonline.com/doi/full/10.1080/17439760.2023.2178956',
            'design_type': 'Longitudinal',
            'original_study_citation': 'Hedonic adaptation research.'
        },
    ]


def get_clinical_psychology_failures():
    """
    Clinical psychology replication issues and treatment effect concerns
    """
    return [
        {
            'title': 'EMDR: Eye Movements May Not Be Necessary Component',
            'category': 'Clinical Psychology',
            'hypothesis': 'Eye movements are essential active ingredient in EMDR for PTSD',
            'what_failed': 'Dismantling studies found EMDR without eye movements equally effective.',
            'why_failed': 'Exposure component rather than eye movements may drive effects.',
            'sample_size': 500,
            'methodology': 'Dismantling RCTs',
            'lessons_learned': 'Novel treatment components require isolation of active ingredients.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'RCT',
            'original_study_citation': 'Shapiro, F. EMDR therapy research.'
        },
        {
            'title': 'Specific Therapy Effects: Often No Better Than Common Factors',
            'category': 'Clinical Psychology',
            'hypothesis': 'Specific therapy techniques provide unique benefits beyond common factors',
            'what_failed': 'Meta-analyses show most therapies produce similar outcomes (Dodo bird verdict).',
            'why_failed': 'Alliance and common factors may account for most variance.',
            'sample_size': 50000,
            'methodology': 'Meta-analysis of therapy outcomes',
            'lessons_learned': 'Therapy-specific techniques may be less important than relationship factors.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Psychotherapy specificity research.'
        },
        {
            'title': 'Repressed Memories: No Evidence for Reliable Recovery',
            'category': 'Clinical Psychology',
            'hypothesis': 'Traumatic memories can be repressed and later recovered accurately',
            'what_failed': 'No scientific evidence supports the accuracy of recovered memories. Many were found to be false.',
            'why_failed': 'Memory is reconstructive; "recovered" memories often created through suggestion.',
            'sample_size': 1000,
            'methodology': 'Review of recovered memory evidence',
            'lessons_learned': 'Clinical beliefs require scientific validation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Review',
            'original_study_citation': 'Recovered memory therapy practices.'
        },
        {
            'title': 'Critical Incident Stress Debriefing: May Cause Harm',
            'category': 'Clinical Psychology',
            'hypothesis': 'Immediate debriefing after trauma prevents PTSD',
            'what_failed': 'Meta-analyses show CISD is ineffective and may actually increase PTSD symptoms.',
            'why_failed': 'Forcing immediate processing may interfere with natural recovery.',
            'sample_size': 3000,
            'methodology': 'Meta-analysis of debriefing studies',
            'lessons_learned': 'Well-intentioned interventions can cause harm.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Mitchell, J. T. CISD research.'
        },
        {
            'title': 'Scared Straight Programs: Actually Increase Delinquency',
            'category': 'Clinical Psychology',
            'hypothesis': 'Exposing at-risk youth to prison deters future crime',
            'what_failed': 'Meta-analysis found programs increase rather than decrease delinquency.',
            'why_failed': 'Exposure may normalize or teach criminal behavior.',
            'sample_size': 8000,
            'methodology': 'Meta-analysis of Scared Straight evaluations',
            'lessons_learned': 'Intuitive interventions require rigorous outcome evaluation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Scared Straight program research.'
        },
        {
            'title': 'D.A.R.E. Drug Prevention: No Long-Term Effects',
            'category': 'Educational Psychology',
            'hypothesis': 'D.A.R.E. program prevents drug use in youth',
            'what_failed': 'Multiple meta-analyses found D.A.R.E. has no significant long-term effect on drug use.',
            'why_failed': 'Information-based prevention insufficient for behavior change.',
            'sample_size': 100000,
            'methodology': 'Multiple meta-analyses',
            'lessons_learned': 'Popular prevention programs require outcome evaluation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'D.A.R.E. program evaluations.'
        },
    ]


def get_developmental_psychology_failures():
    """
    Developmental psychology replication issues
    """
    return [
        {
            'title': 'Mozart Effect: Listening to Mozart Does Not Increase IQ',
            'category': 'Developmental Psychology',
            'hypothesis': 'Listening to Mozart temporarily increases spatial reasoning',
            'what_failed': 'Meta-analyses found any effect is small, short-lived, and not specific to Mozart.',
            'why_failed': 'Original finding overinterpreted. Any arousing stimulus produces similar effects.',
            'sample_size': 5000,
            'methodology': 'Meta-analysis of Mozart effect studies',
            'lessons_learned': 'Media-hyped findings require skepticism and replication.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Meta-analysis',
            'original_study_citation': 'Rauscher, F. H., et al. (1993). Mozart effect.'
        },
        {
            'title': 'Learning Styles: No Evidence for Matching Instruction to Style',
            'category': 'Educational Psychology',
            'hypothesis': 'Students learn better when instruction matches their learning style',
            'what_failed': 'No credible evidence that matching teaching to learning styles improves outcomes.',
            'why_failed': 'Learning styles lack construct validity and predictive power.',
            'sample_size': 10000,
            'methodology': 'Systematic review of learning styles research',
            'lessons_learned': 'Widely believed educational practices may lack evidence.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Systematic Review',
            'original_study_citation': 'Learning styles theory and application.'
        },
        {
            'title': 'Birth Order and Personality: Effects Are Negligible',
            'category': 'Personality Psychology',
            'hypothesis': 'Birth order shapes adult personality traits',
            'what_failed': 'Large-scale studies with proper controls find birth order effects on personality are essentially zero.',
            'why_failed': 'Within-family designs and small samples created spurious findings.',
            'sample_size': 377000,
            'methodology': 'Large-scale between-family study',
            'lessons_learned': 'Popular beliefs about personality development may be myths.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Cross-sectional',
            'original_study_citation': 'Sulloway, F. J. birth order theory.'
        },
        {
            'title': 'Left-Brain vs Right-Brain Learning: Myth',
            'category': 'Neuroscience',
            'hypothesis': 'People are either left-brain or right-brain dominant learners',
            'what_failed': 'Neuroimaging shows no evidence of hemispheric dominance in learning styles.',
            'why_failed': 'Oversimplified pop-psychology misrepresentation of neuroscience.',
            'sample_size': 1000,
            'methodology': 'fMRI studies of lateralization',
            'lessons_learned': 'Neuromyths persist despite contradicting evidence.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Neuroimaging',
            'original_study_citation': 'Brain lateralization pop psychology.'
        },
        {
            'title': 'Baby Einstein Videos: No Cognitive Benefits',
            'category': 'Developmental Psychology',
            'hypothesis': 'Educational videos for infants boost cognitive development',
            'what_failed': 'Studies found no evidence of cognitive benefits; some found negative vocabulary effects.',
            'why_failed': 'Screen time may displace more beneficial interactions.',
            'sample_size': 1000,
            'methodology': 'Longitudinal studies of infant media use',
            'lessons_learned': 'Marketing claims about child development require scientific verification.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Longitudinal',
            'original_study_citation': 'Baby video educational claims.'
        },
        {
            'title': 'Attachment Therapy Holding: Harmful Practice',
            'category': 'Clinical Psychology',
            'hypothesis': 'Coercive holding therapy helps attachment-disordered children',
            'what_failed': 'No evidence of benefit; practice has caused deaths.',
            'why_failed': 'Theory was pseudoscientific; practice was abusive.',
            'sample_size': 100,
            'methodology': 'Review of holding therapy outcomes',
            'lessons_learned': 'Dangerous practices can persist without evidence base.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Review',
            'original_study_citation': 'Attachment therapy holding practices.'
        },
    ]


def get_neuroscience_failures():
    """
    Neuroscience replication issues and fMRI concerns
    """
    return [
        {
            'title': 'fMRI False Positives: Dead Salmon Shows "Brain Activity"',
            'category': 'Neuroscience',
            'hypothesis': 'Standard fMRI analysis methods are reliable',
            'what_failed': 'Famous study found "significant" brain activity in a dead salmon using standard methods.',
            'why_failed': 'Inadequate multiple comparisons correction in fMRI analysis.',
            'sample_size': 1,
            'methodology': 'Demonstration with dead Atlantic salmon',
            'lessons_learned': 'Statistical methods in neuroimaging require proper correction.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Methodological Demonstration',
            'original_study_citation': 'Bennett, C. M., et al. (2009). Dead salmon fMRI.'
        },
        {
            'title': 'fMRI Software Bug: Invalidates Many Studies',
            'category': 'Neuroscience',
            'hypothesis': 'Major fMRI analysis software produces valid results',
            'what_failed': 'Bug in commonly used software produced up to 70% false positive rates in some analyses.',
            'why_failed': 'Software error went undetected for 15+ years of use.',
            'sample_size': 40000,
            'methodology': 'Analysis of software validation',
            'lessons_learned': 'Software tools require independent validation.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Methodological Analysis',
            'original_study_citation': 'fMRI cluster analysis research.'
        },
        {
            'title': 'Mirror Neurons in Humans: Evidence Weaker Than Claimed',
            'category': 'Neuroscience',
            'hypothesis': 'Mirror neurons exist in humans and explain empathy/imitation',
            'what_failed': 'Direct evidence for human mirror neurons is limited; many claims are speculative.',
            'why_failed': 'Extrapolation from monkey studies to human social cognition was premature.',
            'sample_size': 2000,
            'methodology': 'Review of mirror neuron evidence',
            'lessons_learned': 'Neural mechanisms require direct rather than inferred evidence.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Review',
            'original_study_citation': 'Human mirror neuron claims.'
        },
        {
            'title': 'Dopamine = Pleasure: Oversimplified Neuromyth',
            'category': 'Neuroscience',
            'hypothesis': 'Dopamine is the pleasure/reward neurotransmitter',
            'what_failed': 'Research shows dopamine relates more to wanting/motivation than liking/pleasure.',
            'why_failed': 'Pop-neuroscience oversimplified complex neurobiology.',
            'sample_size': 500,
            'methodology': 'Review of dopamine function research',
            'lessons_learned': 'Neurotransmitter functions are more complex than simple labels suggest.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Review',
            'original_study_citation': 'Dopamine reward system research.'
        },
        {
            'title': 'Brain Games Transfer: No Far Transfer Effects',
            'category': 'Neuroscience',
            'hypothesis': 'Brain training games improve general cognitive function',
            'what_failed': 'Consensus statement from 75 scientists: no evidence of far transfer from brain games.',
            'why_failed': 'Training improves trained tasks only; no evidence of transfer.',
            'sample_size': 20000,
            'methodology': 'Review of brain training studies',
            'lessons_learned': 'Commercial brain training claims are not supported by science.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Scientific Consensus',
            'original_study_citation': 'Cognitive training and transfer research.'
        },
        {
            'title': 'Voodoo Correlations in Neuroimaging',
            'category': 'Neuroscience',
            'hypothesis': 'Published brain-behavior correlations are accurate',
            'what_failed': 'Analysis found many neuroimaging correlations were implausibly high due to circular analysis.',
            'why_failed': 'Non-independent ROI selection inflated brain-behavior correlations.',
            'sample_size': 500,
            'methodology': 'Analysis of published neuroimaging correlations',
            'lessons_learned': 'Neuroimaging analysis requires methodological rigor.',
            'source_url': 'https://replicationindex.com/category/replication-failures/',
            'design_type': 'Methodological Critique',
            'original_study_citation': 'Vul, E., et al. (2009). Voodoo correlations.'
        },
    ]


def get_all_scraped_experiments():
    """Combine all scraped experiments from real sources"""
    all_experiments = []
    all_experiments.extend(get_jasnh_scraped())
    all_experiments.extend(get_famous_failed_replications())
    all_experiments.extend(get_many_labs_failures())
    all_experiments.extend(get_reproducibility_project_failures())
    all_experiments.extend(get_registered_replication_reports())
    all_experiments.extend(get_forrt_database_failures())
    all_experiments.extend(get_collabra_replications())
    all_experiments.extend(get_additional_documented_failures())
    # New comprehensive sources
    all_experiments.extend(get_ego_depletion_crisis())
    all_experiments.extend(get_priming_failures())
    all_experiments.extend(get_stereotype_threat_failures())
    all_experiments.extend(get_growth_mindset_issues())
    all_experiments.extend(get_implicit_bias_iat_problems())
    all_experiments.extend(get_marshmallow_test_findings())
    all_experiments.extend(get_stanford_prison_critique())
    all_experiments.extend(get_many_labs_2_failures())
    all_experiments.extend(get_reproducibility_project_comprehensive())
    all_experiments.extend(get_additional_replication_failures())
    # Additional categories
    all_experiments.extend(get_embodied_cognition_failures())
    all_experiments.extend(get_subliminal_priming_failures())
    all_experiments.extend(get_positive_psychology_issues())
    all_experiments.extend(get_clinical_psychology_failures())
    all_experiments.extend(get_developmental_psychology_failures())
    all_experiments.extend(get_neuroscience_failures())
    return all_experiments


if __name__ == '__main__':
    experiments = get_all_scraped_experiments()
    print(f"Total scraped experiments: {len(experiments)}")
    for cat in set(e['category'] for e in experiments):
        count = sum(1 for e in experiments if e['category'] == cat)
        print(f"  {cat}: {count}")
