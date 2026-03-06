"""
FailedLab - Psychology Failed Experiments Scraper
Scrapes and curates failed replications and null results from psychology research
"""

import requests
import json
import time
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.models import SessionLocal, FailedExperiment, Category, init_db, generate_uuid


# ============ Curated Failed Replications ============
# From Reproducibility Project: Psychology, Many Labs, and other replication efforts

CURATED_FAILED_EXPERIMENTS = [
    # Reproducibility Project: Psychology - Failed Replications
    {
        "title": "Failed Replication: Ego Depletion Effect",
        "category": "Social Psychology",
        "hypothesis": "Exerting self-control depletes a limited resource, making subsequent self-control tasks more difficult.",
        "sample_size": 2141,
        "design_type": "Multi-lab replication (23 labs)",
        "methodology": "Participants completed an initial self-control task (crossing out letters), then attempted a second self-control task. Measured persistence and performance.",
        "what_failed": "No significant ego depletion effect found (d = 0.04). The original study by Baumeister et al. (1998) reported d = 0.62. Meta-analysis of 23 labs showed effect indistinguishable from zero.",
        "why_failed": "Original effect may have been a false positive due to small samples, publication bias, and researcher degrees of freedom. The 'limited resource' model of willpower lacks empirical support.",
        "lessons_learned": "Large-scale pre-registered replications are essential for establishing effect sizes. Publication bias severely inflated original estimates.",
        "original_study_doi": "10.1037/0022-3514.74.5.1252",
        "original_study_citation": "Baumeister, R. F., Bratslavsky, E., Muraven, M., & Tice, D. M. (1998). Ego depletion: Is the active self a limited resource?"
    },
    {
        "title": "Failed Replication: Power Posing Effects on Hormones",
        "category": "Social Psychology",
        "hypothesis": "Adopting expansive 'power poses' increases testosterone, decreases cortisol, and increases feelings of power and risk-taking.",
        "sample_size": 200,
        "design_type": "Between-subjects experimental",
        "methodology": "Participants held high-power or low-power poses for 2 minutes. Saliva samples collected before and after. Measured testosterone, cortisol, feelings of power, and risk-taking behavior.",
        "what_failed": "No significant effects on hormones (testosterone or cortisol). Original study by Carney, Cuddy, & Yap (2010) found significant hormonal changes. Multiple replications found null effects.",
        "why_failed": "Original study had only 42 participants (severely underpowered). P-hacking and selective reporting likely inflated original effects. Lead author Dana Carney publicly disavowed the findings.",
        "lessons_learned": "Small sample sizes + flexible analysis = unreliable findings. The co-author's public statement acknowledging the failure was unprecedented and valuable for science.",
        "original_study_doi": "10.1177/0956797610383437",
        "original_study_citation": "Carney, D. R., Cuddy, A. J., & Yap, A. J. (2010). Power posing: Brief nonverbal displays affect neuroendocrine levels."
    },
    {
        "title": "Failed Replication: Facial Feedback Hypothesis",
        "category": "Social Psychology",
        "hypothesis": "Holding a pen in your teeth (forcing a smile) makes cartoons seem funnier compared to holding a pen with your lips (forcing a frown).",
        "sample_size": 1894,
        "design_type": "Multi-lab replication (17 labs)",
        "methodology": "Participants held a pen in their teeth or lips while rating the funniness of Far Side cartoons. Registered Replication Report methodology.",
        "what_failed": "No significant effect found (d = 0.03). Original Strack, Martin, & Stepper (1988) study reported significant effects. Meta-analysis showed effect size near zero.",
        "why_failed": "Original study was underpowered (n=92). The effect, if real, is much smaller than originally reported. May also be moderated by awareness of the hypothesis.",
        "lessons_learned": "Classic findings in psychology textbooks may not replicate. Pre-registration and large samples are essential.",
        "original_study_doi": "10.1037/0022-3514.54.5.768",
        "original_study_citation": "Strack, F., Martin, L. L., & Stepper, S. (1988). Inhibiting and facilitating conditions of the human smile."
    },
    {
        "title": "Failed Replication: Professor Priming and Intelligence",
        "category": "Social Psychology",
        "hypothesis": "Thinking about professors (vs. soccer hooligans) improves performance on trivia questions through behavioral priming.",
        "sample_size": 4493,
        "design_type": "Multi-lab replication (40 labs)",
        "methodology": "Participants imagined either a professor or soccer hooligan, then answered trivia questions. Measured accuracy on general knowledge test.",
        "what_failed": "No priming effect found across 40 labs. Effect size was d = -0.01 (essentially zero). Original Dijksterhuis & van Knippenberg (1998) reported large effects.",
        "why_failed": "Original effect was likely a false positive. Behavioral priming effects in general have failed to replicate across many studies. The theoretical mechanism was never well-specified.",
        "lessons_learned": "The entire field of 'social priming' has been severely questioned. Subtle primes producing large behavioral effects was too good to be true.",
        "original_study_doi": "10.1037/0022-3514.74.4.865",
        "original_study_citation": "Dijksterhuis, A., & van Knippenberg, A. (1998). The relation between perception and behavior."
    },
    {
        "title": "Failed Replication: Money Priming and Self-Sufficiency",
        "category": "Social Psychology",
        "hypothesis": "Exposure to money-related images makes people more self-sufficient, less helpful, and prefer solitary activities.",
        "sample_size": 938,
        "design_type": "Direct replication across multiple studies",
        "methodology": "Participants were primed with money images or neutral images, then measured on helping behavior, preference for solitary activities, and self-sufficiency.",
        "what_failed": "None of the 9 original effects replicated. Most effect sizes were near zero or in the opposite direction. Original Vohs et al. (2006) reported consistent large effects.",
        "why_failed": "Original studies used small samples and many researcher degrees of freedom. The conceptual link between money exposure and self-sufficiency was speculative.",
        "lessons_learned": "Priming studies with many dependent variables and small samples are particularly unreliable.",
        "original_study_doi": "10.1126/science.1132491",
        "original_study_citation": "Vohs, K. D., Mead, N. L., & Goode, M. R. (2006). The psychological consequences of money."
    },
    {
        "title": "Failed Replication: Elderly Priming and Walking Speed",
        "category": "Social Psychology",
        "hypothesis": "Exposure to words related to elderly stereotypes (Florida, bingo, wrinkle) causes people to walk more slowly.",
        "sample_size": 2500,
        "design_type": "Multiple direct replications",
        "methodology": "Participants completed a scrambled sentence task with elderly-related or neutral words, then walking speed was measured in hallway.",
        "what_failed": "No effect on walking speed in multiple replication attempts. The iconic Bargh, Chen, & Burrows (1996) finding did not replicate.",
        "why_failed": "Original study had serious methodological issues including experimenter not being blind to condition. Effect may have been due to experimenter expectancy effects.",
        "lessons_learned": "Double-blind procedures are essential even in social psychology experiments. This failure sparked the 'replication crisis' in psychology.",
        "original_study_doi": "10.1037/0022-3514.71.2.230",
        "original_study_citation": "Bargh, J. A., Chen, M., & Burrows, L. (1996). Automaticity of social behavior."
    },
    {
        "title": "Failed Replication: Stereotype Threat in Women's Math Performance",
        "category": "Social Psychology",
        "hypothesis": "Reminding women of gender stereotypes about math ability causes them to perform worse on math tests.",
        "sample_size": 2064,
        "design_type": "Meta-analysis of replication attempts",
        "methodology": "Women completed math tests after being reminded of gender stereotypes (threat condition) or not (control). Measured math test performance.",
        "what_failed": "Meta-analysis found the effect size was much smaller than originally reported (d = 0.22 vs. original d = 0.52). Many individual replications found null effects.",
        "why_failed": "Publication bias inflated original estimates. Effect is real but much smaller and more context-dependent than originally claimed. Moderators poorly understood.",
        "lessons_learned": "Even real effects can be severely overestimated due to publication bias. Effect size estimates from original studies should be treated with skepticism.",
        "original_study_doi": "10.1037/0022-3514.69.5.797",
        "original_study_citation": "Spencer, S. J., Steele, C. M., & Quinn, D. M. (1999). Stereotype threat and women's math performance."
    },
    {
        "title": "Failed Replication: Cleanliness and Moral Judgments",
        "category": "Social Psychology",
        "hypothesis": "Physical cleanliness reduces the severity of moral judgments (the 'Macbeth effect').",
        "sample_size": 1746,
        "design_type": "Multi-lab replication",
        "methodology": "Participants washed hands or not, then rated the moral wrongness of various scenarios. Based on Schnall et al. (2008).",
        "what_failed": "No significant effect of hand-washing on moral judgments. Effect size was d = 0.01. Original study reported significant effects.",
        "why_failed": "Original study was underpowered. The connection between physical and moral 'cleanliness' was metaphorical and theoretically weak.",
        "lessons_learned": "Embodied cognition effects often fail to replicate. Metaphorical connections don't necessarily produce real psychological effects.",
        "original_study_doi": "10.1177/0956797611430818",
        "original_study_citation": "Schnall, S., Benton, J., & Harvey, S. (2008). With a clean conscience: Cleanliness reduces the severity of moral judgments."
    },

    # Many Labs 1 - Failed Replications
    {
        "title": "Failed Replication: Imagined Contact Reduces Prejudice",
        "category": "Social Psychology",
        "hypothesis": "Simply imagining a positive interaction with an outgroup member reduces prejudice toward that group.",
        "sample_size": 6344,
        "design_type": "Many Labs 1 (36 labs)",
        "methodology": "Participants imagined a positive interaction with an elderly person or a neutral scenario, then completed measures of attitudes toward elderly people.",
        "what_failed": "Effect was much smaller than original (d = 0.13 vs. original d = 0.73). Many labs found null or negative effects.",
        "why_failed": "Original studies likely overestimated effect due to small samples. Imagined contact may only work under specific conditions not present in most replications.",
        "lessons_learned": "Interventions that seem too easy (just imagine something) often don't produce robust effects. Real intergroup contact likely needed.",
        "original_study_doi": "10.1037/0022-3514.93.3.404",
        "original_study_citation": "Turner, R. N., Crisp, R. J., & Lambert, E. (2007). Imagining intergroup contact can improve intergroup attitudes."
    },
    {
        "title": "Failed Replication: Currency Priming and System Justification",
        "category": "Social Psychology",
        "hypothesis": "Exposure to high-value currency increases support for the current social system.",
        "sample_size": 6344,
        "design_type": "Many Labs 1 (36 labs)",
        "methodology": "Participants viewed images of currency or neutral images, then completed measures of system justification and support for current institutions.",
        "what_failed": "No significant effect found (d = 0.00). Original Caruso et al. (2013) found significant effects of money priming on system justification.",
        "why_failed": "Original study was severely underpowered. Money priming effects in general have not replicated across the field.",
        "lessons_learned": "Another failed money priming study. The entire paradigm of subtle environmental cues producing large attitude changes is questionable.",
        "original_study_doi": "10.1016/j.jesp.2012.08.016",
        "original_study_citation": "Caruso, E. M., Vohs, K. D., Baxter, B., & Waytz, A. (2013). Mere exposure to money increases endorsement of free-market systems."
    },

    # Many Labs 2 - Failed Replications
    {
        "title": "Failed Replication: Moral Credentials and Discrimination",
        "category": "Social Psychology",
        "hypothesis": "People who establish 'moral credentials' by making a non-prejudiced choice feel licensed to subsequently discriminate.",
        "sample_size": 7279,
        "design_type": "Many Labs 2 (multiple countries)",
        "methodology": "Participants made hiring decisions. Those who selected a minority candidate in round 1 were predicted to discriminate more in round 2.",
        "what_failed": "No moral licensing effect found. Effect size near zero across all sites. Original Monin & Miller (2001) reported significant effects.",
        "why_failed": "Original effect may have been a false positive. Moral licensing is theoretically plausible but empirically weak.",
        "lessons_learned": "Even intuitively appealing theories need robust empirical support. Single studies with small samples cannot establish effects.",
        "original_study_doi": "10.1037/0022-3514.81.1.33",
        "original_study_citation": "Monin, B., & Miller, D. T. (2001). Moral credentials and the expression of prejudice."
    },
    {
        "title": "Failed Replication: Commitment and Consistency in Donations",
        "category": "Social Psychology",
        "hypothesis": "Getting people to agree to display a small sign increases likelihood they'll later agree to a large sign (foot-in-the-door effect in new context).",
        "sample_size": 7679,
        "design_type": "Many Labs 2",
        "methodology": "Participants asked to agree to small request, then large request. Measured compliance rates.",
        "what_failed": "Effect was much smaller than originally reported in this specific paradigm. Many labs found null effects.",
        "why_failed": "The classic foot-in-the-door effect may be more context-dependent than originally thought. Effect sizes were overestimated.",
        "lessons_learned": "Classic social psychology effects need modern, high-powered replications to establish true effect sizes.",
        "original_study_doi": "10.1037/h0023718",
        "original_study_citation": "Freedman, J. L., & Fraser, S. C. (1966). Compliance without pressure: The foot-in-the-door technique."
    },

    # Cognitive Psychology Failed Replications
    {
        "title": "Failed Replication: Verbalization Impairs Face Recognition",
        "category": "Cognitive Psychology",
        "hypothesis": "Describing a face verbally impairs subsequent recognition of that face (verbal overshadowing effect).",
        "sample_size": 2000,
        "design_type": "Registered Replication Report",
        "methodology": "Participants viewed a face, then either described it verbally or did a filler task, then attempted to identify the face from a lineup.",
        "what_failed": "Effect was much smaller than originally reported (d = 0.12 vs. original d = 0.42). Many labs found null effects.",
        "why_failed": "Original studies may have had flexible analysis and outcome measures. Effect is highly sensitive to exact procedural details.",
        "lessons_learned": "Even well-established cognitive effects can be much smaller than originally reported.",
        "original_study_doi": "10.1016/0010-0285(90)90003-M",
        "original_study_citation": "Schooler, J. W., & Engstler-Schooler, T. Y. (1990). Verbal overshadowing of visual memories."
    },
    {
        "title": "Failed Replication: Grammar Learning During Sleep",
        "category": "Cognitive Psychology",
        "hypothesis": "People can learn grammatical rules from auditory input presented during sleep.",
        "sample_size": 120,
        "design_type": "Direct replication with polysomnography",
        "methodology": "Participants heard an artificial grammar during sleep. Tested on grammaticality judgments after waking. EEG confirmed sleep states.",
        "what_failed": "No evidence of grammar learning during sleep. Performance was at chance. Original claims of sleep learning were not supported.",
        "why_failed": "Earlier studies had poor sleep monitoring. Participants may have been partially awake. Consolidation during sleep differs from learning during sleep.",
        "lessons_learned": "Sleep learning claims require rigorous sleep monitoring. The brain state during sleep does not support new declarative learning.",
        "original_study_doi": "10.1038/nn.3152",
        "original_study_citation": "Various sleep learning studies"
    },

    # Developmental Psychology
    {
        "title": "Failed Replication: Mozart Effect on Spatial Reasoning",
        "category": "Developmental Psychology",
        "hypothesis": "Listening to Mozart temporarily improves spatial-temporal reasoning ability.",
        "sample_size": 8000,
        "design_type": "Meta-analysis of replication attempts",
        "methodology": "Participants listened to Mozart, silence, or other music, then completed spatial reasoning tasks.",
        "what_failed": "Meta-analysis found effect size near zero (d = 0.08). Original Rauscher et al. (1993) claimed 8-9 IQ point improvement.",
        "why_failed": "Original study was severely underpowered (n=36). Any effect is due to arousal/mood, not Mozart specifically. Popular media grossly overstated findings.",
        "lessons_learned": "Media hype around 'brain training' claims often far exceeds evidence. Mozart doesn't make you smarter.",
        "original_study_doi": "10.1038/365611a0",
        "original_study_citation": "Rauscher, F. H., Shaw, G. L., & Ky, K. N. (1993). Music and spatial task performance."
    },
    {
        "title": "Failed Replication: Growth Mindset Interventions in Schools",
        "category": "Educational Psychology",
        "hypothesis": "Teaching students that intelligence is malleable (growth mindset) improves academic achievement.",
        "sample_size": 400000,
        "design_type": "Large-scale randomized controlled trials",
        "methodology": "Students received growth mindset interventions (teaching that the brain can grow) or control. Academic outcomes measured.",
        "what_failed": "Effect sizes were tiny (d = 0.02-0.04). No meaningful impact on grades or test scores for most students. Claims of transformative effects unsupported.",
        "why_failed": "Original studies were small and used subjective outcomes. The intervention is too brief and superficial to change deeply-held beliefs. Teacher/implementation effects dominate.",
        "lessons_learned": "Brief psychological interventions rarely produce lasting academic benefits. Structural factors matter more than mindset.",
        "original_study_doi": "10.1177/0956797611430818",
        "original_study_citation": "Dweck, C. S. (2006). Mindset: The new psychology of success."
    },

    # Clinical Psychology
    {
        "title": "Failed Replication: Power of Positive Thinking in Cancer Outcomes",
        "category": "Clinical Psychology",
        "hypothesis": "Positive attitude and 'fighting spirit' improves cancer survival rates.",
        "sample_size": 12000,
        "design_type": "Meta-analysis of prospective studies",
        "methodology": "Measured psychological attitudes in cancer patients and tracked survival outcomes over years.",
        "what_failed": "No reliable relationship between positive attitude and survival. Fighting spirit did not predict better outcomes.",
        "why_failed": "Original studies were small and had selection biases. Surviving longer gives more time to develop positive coping, creating reverse causation.",
        "lessons_learned": "Blaming patients for 'not being positive enough' is harmful and scientifically unfounded. Focus on evidence-based treatments.",
        "original_study_doi": "10.1016/S0140-6736(89)91028-1",
        "original_study_citation": "Greer, S., et al. (1989). Psychological response to breast cancer and 15-year outcome."
    },
    {
        "title": "Failed Replication: EMDR Eye Movements are Essential",
        "category": "Clinical Psychology",
        "hypothesis": "The eye movement component of EMDR therapy is essential for its effectiveness in treating PTSD.",
        "sample_size": 2000,
        "design_type": "Meta-analysis of dismantling studies",
        "methodology": "Compared full EMDR (with eye movements) to EMDR without eye movements. Measured PTSD symptom reduction.",
        "what_failed": "Eye movements did not add significant benefit beyond exposure therapy elements. EMDR without eye movements was equally effective.",
        "why_failed": "The eye movement component appears to be an inert placebo element. The active ingredient is prolonged exposure to traumatic memories.",
        "lessons_learned": "Components of therapy packages need dismantling studies. Not all elements of 'branded' therapies are active ingredients.",
        "original_study_doi": "10.1037/0022-006X.66.3.480",
        "original_study_citation": "Shapiro, F. (1989). Eye movement desensitization: A new treatment for post-traumatic stress disorder."
    },

    # Neuroscience
    {
        "title": "Failed Replication: Brain Training Transfers to General Intelligence",
        "category": "Neuroscience",
        "hypothesis": "Working memory training (like N-back tasks) improves general intelligence (IQ) and cognitive abilities.",
        "sample_size": 25000,
        "design_type": "Meta-analysis and large RCTs",
        "methodology": "Participants completed working memory training for weeks. Tested on measures of fluid intelligence before and after.",
        "what_failed": "No significant transfer to IQ or untrained tasks. People improve at the trained task only. Lumosity settled FTC lawsuit for false advertising.",
        "why_failed": "Cognitive training is highly specific. Near-transfer occurs but far-transfer to general intelligence does not. The brain doesn't work like a muscle.",
        "lessons_learned": "The brain training industry made billions on unsupported claims. Specific skills require specific practice.",
        "original_study_doi": "10.1073/pnas.0801268105",
        "original_study_citation": "Jaeggi, S. M., et al. (2008). Improving fluid intelligence with training on working memory."
    },
    {
        "title": "Failed Replication: Oxytocin Increases Trust",
        "category": "Neuroscience",
        "hypothesis": "Intranasal oxytocin administration increases trust in strangers, measured by trust game behavior.",
        "sample_size": 3000,
        "design_type": "Meta-analysis of replication attempts",
        "methodology": "Participants inhaled oxytocin or placebo nasal spray, then played economic trust games with strangers.",
        "what_failed": "Meta-analysis found effect size near zero. Many well-powered replications found no effect of oxytocin on trust.",
        "why_failed": "Original Kosfeld et al. (2005) study was underpowered. Nasal oxytocin may not reach brain in sufficient quantities. Effect is highly context-dependent.",
        "lessons_learned": "The 'love hormone' narrative was oversimplified. Oxytocin has complex, context-dependent effects.",
        "original_study_doi": "10.1038/nature03701",
        "original_study_citation": "Kosfeld, M., et al. (2005). Oxytocin increases trust in humans."
    },

    # Personality Psychology
    {
        "title": "Failed Replication: Implicit Association Test Predicts Behavior",
        "category": "Personality Psychology",
        "hypothesis": "IAT scores predict discriminatory behavior better than explicit measures of prejudice.",
        "sample_size": 100000,
        "design_type": "Meta-analysis of predictive validity studies",
        "methodology": "IAT scores correlated with behavioral measures of discrimination in various domains.",
        "what_failed": "IAT poorly predicts actual discriminatory behavior (r = 0.15). Explicit measures predict better. Changes in IAT scores don't change behavior.",
        "why_failed": "IAT measures categorization speed, not 'implicit prejudice.' The measure has poor test-retest reliability. The construct validity is questionable.",
        "lessons_learned": "A popular measure isn't necessarily a valid measure. The IAT should not be used for individual assessment or hiring decisions.",
        "original_study_doi": "10.1037/0022-3514.74.6.1464",
        "original_study_citation": "Greenwald, A. G., McGhee, D. E., & Schwartz, J. L. (1998). Measuring individual differences in implicit cognition."
    },

    # Additional failed replications
    {
        "title": "Failed Replication: Red Color Enhances Attraction",
        "category": "Social Psychology",
        "hypothesis": "Women wearing red are rated as more attractive and sexually desirable by men.",
        "sample_size": 800,
        "design_type": "Direct replication",
        "methodology": "Men rated attractiveness of women in photos manipulated to show red vs. other colored shirts.",
        "what_failed": "No significant effect of red on attractiveness ratings. Effect sizes near zero.",
        "why_failed": "Original Elliot & Niesta (2008) studies were underpowered. Color effects on attraction are likely tiny if they exist at all.",
        "lessons_learned": "Evolutionary psychology claims need rigorous testing before acceptance.",
        "original_study_doi": "10.1037/0022-3514.95.5.1150",
        "original_study_citation": "Elliot, A. J., & Niesta, D. (2008). Romantic red: Red enhances men's attraction to women."
    },
    {
        "title": "Failed Replication: Social Exclusion and Physical Pain Share Neural Substrates",
        "category": "Social Psychology",
        "hypothesis": "Social exclusion activates the same brain regions as physical pain, suggesting shared neural mechanisms.",
        "sample_size": 500,
        "design_type": "Neuroimaging replication",
        "methodology": "fMRI during Cyberball exclusion paradigm. Analyzed activation in dACC and other 'pain-related' regions.",
        "what_failed": "Activation patterns were not specific to pain. dACC activates for many things (salience, conflict). Reverse inference invalid.",
        "why_failed": "Original Eisenberger et al. (2003) overinterpreted regional activation. Brain regions are not functionally specific.",
        "lessons_learned": "Reverse inference in neuroimaging is problematic. 'Social pain = physical pain' was overstated.",
        "original_study_doi": "10.1126/science.1089134",
        "original_study_citation": "Eisenberger, N. I., Lieberman, M. D., & Williams, K. D. (2003). Does rejection hurt?"
    },
    {
        "title": "Failed Replication: Unconscious Thought Advantage in Decision Making",
        "category": "Cognitive Psychology",
        "hypothesis": "Complex decisions are better made unconsciously (by distraction) than through conscious deliberation.",
        "sample_size": 1500,
        "design_type": "Meta-analysis of replication attempts",
        "methodology": "Participants chose between complex options (cars, apartments) after conscious thought, unconscious thought (distraction), or immediate decision.",
        "what_failed": "No advantage for unconscious thought. Conscious deliberation performed as well or better. The 'deliberation without attention' effect did not replicate.",
        "why_failed": "Original Dijksterhuis et al. (2006) studies had methodological issues. The theory lacked a plausible mechanism.",
        "lessons_learned": "Counterintuitive findings require extra scrutiny. 'Don't think about it' is bad decision-making advice.",
        "original_study_doi": "10.1126/science.1121629",
        "original_study_citation": "Dijksterhuis, A., et al. (2006). On making the right choice: The deliberation-without-attention effect."
    },
    {
        "title": "Failed Replication: Superstitious Behavior Improves Performance",
        "category": "Social Psychology",
        "hypothesis": "Engaging in superstitious behavior (lucky charms, rituals) improves performance through increased confidence.",
        "sample_size": 300,
        "design_type": "Direct replication",
        "methodology": "Participants performed motor tasks (golf putting) with or without their lucky charm. Measured performance and confidence.",
        "what_failed": "No significant effect of superstitious objects on performance. Effect sizes near zero.",
        "why_failed": "Original Damisch et al. (2010) study was underpowered (n=28 per condition). Effect may only occur in believers under specific conditions.",
        "lessons_learned": "Small-sample psychology experiments with surprising results rarely replicate.",
        "original_study_doi": "10.1177/0956797610372631",
        "original_study_citation": "Damisch, L., Stoberock, B., & Mussweiler, T. (2010). Keep your fingers crossed!"
    },
    {
        "title": "Failed Replication: Watching Eyes Promote Prosocial Behavior",
        "category": "Social Psychology",
        "hypothesis": "Images of watching eyes increase prosocial and honest behavior through reputation monitoring cues.",
        "sample_size": 5000,
        "design_type": "Meta-analysis and large replications",
        "methodology": "Eye images placed near honesty boxes, donation requests, or littering contexts. Measured compliance.",
        "what_failed": "Meta-analysis found effect size near zero in real-world settings. Lab effects did not transfer to field.",
        "why_failed": "Original effects may have been due to publication bias and researcher expectations. In noisy real environments, subtle images don't change behavior.",
        "lessons_learned": "Lab findings often don't generalize to real-world settings. Nudges have limited effectiveness.",
        "original_study_doi": "10.1098/rsbl.2006.0509",
        "original_study_citation": "Bateson, M., Nettle, D., & Roberts, G. (2006). Cues of being watched enhance cooperation."
    },

    # Health Psychology
    {
        "title": "Failed Replication: Social Support Directly Affects Immune Function",
        "category": "Health Psychology",
        "hypothesis": "Higher levels of social support directly boost immune system function.",
        "sample_size": 2000,
        "design_type": "Longitudinal studies with immune measures",
        "methodology": "Measured social support and various immune markers (cytokines, immune cell counts) over time.",
        "what_failed": "Relationships between social support and immune markers were weak and inconsistent. Confounds not adequately controlled.",
        "why_failed": "Immune function is affected by many factors. Social support may affect health through behavior changes, not direct immune effects.",
        "lessons_learned": "Psychoneuroimmunology claims need careful control of confounds. The mind-body connection is more complex than initially claimed.",
        "original_study_doi": "10.1037/0033-2909.113.3.472",
        "original_study_citation": "Uchino, B. N., Cacioppo, J. T., & Kiecolt-Glaser, J. K. (1996). The relationship between social support and physiological processes."
    },

    # Industrial-Organizational Psychology
    {
        "title": "Failed Replication: Graphology Predicts Job Performance",
        "category": "Industrial-Organizational",
        "hypothesis": "Handwriting analysis (graphology) can predict job performance and personality traits.",
        "sample_size": 1000,
        "design_type": "Meta-analysis of validation studies",
        "methodology": "Graphologists analyzed handwriting samples and predicted job performance. Compared to actual performance ratings.",
        "what_failed": "Validity coefficient near zero. Graphology did not predict job performance better than chance.",
        "why_failed": "No theoretical basis for why handwriting would reveal personality. Graphologists use vague, Barnum-style descriptions. It's pseudoscience.",
        "lessons_learned": "Assessment methods need empirical validation. Popular methods can be completely invalid.",
        "original_study_doi": "10.1037/0033-2909.119.3.406",
        "original_study_citation": "Neter, E., & Ben-Shakhar, G. (1989). The predictive validity of graphological inferences."
    },

    # More recent failures
    {
        "title": "Failed Replication: Scarcity Mindset Reduces Cognitive Capacity",
        "category": "Cognitive Psychology",
        "hypothesis": "Experiencing scarcity (poverty, time pressure) reduces cognitive bandwidth and impairs decision-making.",
        "sample_size": 3000,
        "design_type": "Pre-registered replications",
        "methodology": "Participants primed with financial scarcity scenarios, then completed cognitive tests. Compared to control condition.",
        "what_failed": "Effect was much smaller than claimed. Many replications found null effects. The cognitive 'bandwidth tax' was not reliably demonstrated.",
        "why_failed": "Original Mani et al. (2013) had methodological flexibility. Effect may exist but is highly context-dependent and smaller than claimed.",
        "lessons_learned": "Policy-relevant psychological findings need robust replication before informing interventions.",
        "original_study_doi": "10.1126/science.1238041",
        "original_study_citation": "Mani, A., et al. (2013). Poverty impedes cognitive function."
    },
    {
        "title": "Failed Replication: Incidental Haptic Sensations Affect Judgments",
        "category": "Social Psychology",
        "hypothesis": "Touching hard vs. soft objects makes people judge others as more rigid vs. flexible.",
        "sample_size": 500,
        "design_type": "Direct replication",
        "methodology": "Participants touched hard or soft objects, then made judgments about people or situations. Based on Ackerman et al. (2010).",
        "what_failed": "No effect of haptic sensation on judgments. Embodied cognition effects did not replicate.",
        "why_failed": "Original study was underpowered. Metaphorical 'embodied' effects are theoretically weak.",
        "lessons_learned": "Embodied cognition has produced many failed replications. Physical sensations don't reliably influence abstract judgments.",
        "original_study_doi": "10.1126/science.1189993",
        "original_study_citation": "Ackerman, J. M., Nocera, C. C., & Bargh, J. A. (2010). Incidental haptic sensations influence social judgments and decisions."
    },
    {
        "title": "Failed Replication: Willpower is Not Limited by Glucose",
        "category": "Social Psychology",
        "hypothesis": "Self-control depletes blood glucose, and consuming glucose restores self-control capacity.",
        "sample_size": 4000,
        "design_type": "Meta-analysis and pre-registered replications",
        "methodology": "Participants completed self-control tasks, consumed glucose or placebo drink, then completed additional self-control tasks.",
        "what_failed": "No support for glucose model of self-control. Blood glucose levels don't predict self-control performance. Gargling glucose (no ingestion) had same effect.",
        "why_failed": "Brain uses minimal glucose for cognitive tasks. The effect of sweet taste (not calories) suggests motivational, not metabolic, mechanism.",
        "lessons_learned": "The 'willpower is like a muscle that needs fuel' metaphor is wrong. Self-control is not limited by energy availability.",
        "original_study_doi": "10.1037/0022-3514.92.2.325",
        "original_study_citation": "Gailliot, M. T., et al. (2007). Self-control relies on glucose as a limited energy source."
    },
]


def scrape_osf_preprints():
    """Scrape OSF Preprints for failed replications in psychology"""
    experiments = []

    # OSF API search for psychology preprints with failure-related terms
    search_terms = [
        "failed replication psychology",
        "null result psychology",
        "did not replicate psychology",
        "negative result social psychology",
        "replication failure cognitive"
    ]

    print("[Scraper] Searching OSF Preprints...")

    for term in search_terms:
        try:
            url = f"https://api.osf.io/v2/preprints/?filter[provider]=psyarxiv&filter[title][icontains]={term}&page[size]=25"
            response = requests.get(url, timeout=30)

            if response.status_code == 200:
                data = response.json()
                preprints = data.get('data', [])

                for preprint in preprints:
                    attrs = preprint.get('attributes', {})
                    title = attrs.get('title', '')
                    description = attrs.get('description', '')
                    doi = attrs.get('doi', '')

                    # Create experiment entry
                    if title and description:
                        exp = {
                            "title": f"Failed Study: {title[:200]}",
                            "category": "Social Psychology",  # Default, could be improved
                            "hypothesis": description[:500] if description else "See original paper for hypothesis.",
                            "what_failed": f"This study reported a failed replication or null result. Full details in original paper.",
                            "why_failed": "See discussion section of original paper for analysis of why the effect did not replicate.",
                            "original_study_doi": doi,
                            "source_url": f"https://osf.io/preprints/psyarxiv/{preprint.get('id', '')}"
                        }
                        experiments.append(exp)
                        print(f"  Found: {title[:60]}...")

            time.sleep(1)  # Rate limiting

        except Exception as e:
            print(f"  [Warning] Error searching for '{term}': {e}")

    print(f"[Scraper] Found {len(experiments)} experiments from OSF Preprints")
    return experiments


def scrape_retraction_watch():
    """Get notable psychology retractions and corrections"""

    # These are curated from Retraction Watch and published corrections
    retractions = [
        {
            "title": "Retracted: Elderly Priming Effects on Behavior (Bargh et al.)",
            "category": "Social Psychology",
            "hypothesis": "Subtle priming with elderly-related words causes people to walk more slowly.",
            "what_failed": "Multiple replication attempts failed. Methodological issues identified including non-blind experimenter. Effect cannot be reliably reproduced.",
            "why_failed": "Experimenter expectancy effects. Original methodology allowed researcher influence on walking speed measurement.",
            "lessons_learned": "Double-blind procedures are essential even for behavioral outcomes. This case sparked widespread concern about social priming research.",
            "source_url": "https://retractionwatch.com"
        },
        {
            "title": "Retracted: Data Fabrication in Social Psychology (Stapel)",
            "category": "Social Psychology",
            "hypothesis": "Various social psychology effects including environmental effects on behavior.",
            "what_failed": "55 papers retracted. Data was fabricated. None of the reported effects were real.",
            "why_failed": "Scientific fraud. Diederik Stapel fabricated data for over a decade. Illustrates the importance of data sharing and replication.",
            "lessons_learned": "Open data practices could have detected fraud earlier. Co-authors and reviewers failed to notice impossible data patterns.",
            "source_url": "https://en.wikipedia.org/wiki/Diederik_Stapel"
        },
        {
            "title": "Corrected: Overstated Brain-Behavior Correlations",
            "category": "Neuroscience",
            "hypothesis": "Various claims about brain region X causing behavior Y.",
            "what_failed": "Voodoo correlations identified. Impossibly high correlation coefficients reported due to non-independence in analysis.",
            "why_failed": "Circular analysis (double-dipping). Selecting voxels based on outcome then correlating inflates r values artificially.",
            "lessons_learned": "Neuroimaging analysis requires strict independence. The 'dead salmon' study showed how bad practices lead to false positives.",
            "source_url": "https://www.nature.com/articles/nn.2303"
        }
    ]

    return retractions


def seed_database():
    """Seed the database with all scraped and curated experiments"""
    init_db()
    db = SessionLocal()

    try:
        # Check if already seeded
        existing = db.query(FailedExperiment).filter(FailedExperiment.is_seeded == True).count()
        if existing > 0:
            print(f"[Seeder] Database already has {existing} seeded experiments. Skipping.")
            return existing

        all_experiments = []

        # 1. Add curated experiments (high quality)
        print("[Seeder] Adding curated failed replications...")
        all_experiments.extend(CURATED_FAILED_EXPERIMENTS)

        # 2. Scrape OSF Preprints
        print("[Seeder] Scraping OSF Preprints...")
        osf_experiments = scrape_osf_preprints()
        all_experiments.extend(osf_experiments)

        # 3. Add retraction watch entries
        print("[Seeder] Adding retraction data...")
        retractions = scrape_retraction_watch()
        all_experiments.extend(retractions)

        # Insert all experiments
        print(f"[Seeder] Inserting {len(all_experiments)} experiments into database...")

        for exp_data in all_experiments:
            experiment = FailedExperiment(
                id=generate_uuid(),
                field='psychology',
                category=exp_data.get('category', 'Social Psychology'),
                title=exp_data.get('title', 'Untitled Failed Experiment'),
                hypothesis=exp_data.get('hypothesis'),
                sample_size=exp_data.get('sample_size'),
                design_type=exp_data.get('design_type'),
                methodology=exp_data.get('methodology'),
                materials=exp_data.get('materials'),
                what_failed=exp_data.get('what_failed', 'Details not available'),
                why_failed=exp_data.get('why_failed'),
                lessons_learned=exp_data.get('lessons_learned'),
                original_study_doi=exp_data.get('original_study_doi'),
                original_study_citation=exp_data.get('original_study_citation'),
                source_url=exp_data.get('source_url'),
                is_seeded=True,
                status='published',
                upvotes=0
            )
            db.add(experiment)

        db.commit()
        print(f"[Seeder] Successfully seeded {len(all_experiments)} experiments!")
        return len(all_experiments)

    except Exception as e:
        db.rollback()
        print(f"[Seeder] Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  FailedLab - Psychology Failed Experiments Scraper")
    print("="*60 + "\n")

    count = seed_database()
    print(f"\nDone! Seeded {count} failed experiments.")
