"""
Gamma Presentation Generator
Creates presentations using the Create from Template API
"""

import requests
import json

# Your credentials
GAMMA_API_KEY = "sk-gamma-wlYM1BVDdlBCBnVJaUsLAtGY7ikjekJet9xXnuGSu8w"
GAMMA_TEMPLATE_ID = "g_3g8gkijbwnm7wxk"
THEME_ID = "adfbsgcj2cfbfw6"

def generate_presentation(content: str, export_format: str = None):
    """
    Generate a presentation using Gamma's Create from Template API

    Args:
        content: The content/prompt for the presentation
        export_format: Optional - 'pdf' or 'pptx' to get downloadable file

    Returns:
        API response with gamma URL or export link
    """

    url = "https://public-api.gamma.app/v1.0/generations/from-template"

    # Try different auth methods
    headers = {
        "Authorization": f"Bearer {GAMMA_API_KEY}",
        "X-API-Key": GAMMA_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "gammaId": GAMMA_TEMPLATE_ID,
        "prompt": content,
        "themeId": THEME_ID
    }

    # Add export format if specified
    if export_format in ['pdf', 'pptx']:
        payload["exportAs"] = export_format

    print("Sending request to Gamma API...")
    print(f"Template ID: {GAMMA_TEMPLATE_ID}")
    print(f"Theme ID: {THEME_ID}")
    print(f"Content length: {len(content)} characters")

    response = requests.post(url, headers=headers, json=payload)

    print(f"\nResponse Status: {response.status_code}")

    if response.status_code in [200, 201]:
        result = response.json()
        print("\nGeneration started!")
        print(json.dumps(result, indent=2))

        # If we got a generationId, poll for completion
        if 'generationId' in result:
            print("\nPolling for completion...")
            return poll_for_completion(result['generationId'])

        return result
    else:
        print(f"\nError: {response.status_code}")
        print(response.text)
        return None


def poll_for_completion(generation_id: str, max_attempts: int = 30, delay: int = 5):
    """Poll Gamma API until generation is complete"""
    import time

    url = f"https://public-api.gamma.app/v1.0/generations/{generation_id}"
    headers = {
        "Authorization": f"Bearer {GAMMA_API_KEY}",
        "X-API-Key": GAMMA_API_KEY
    }

    for attempt in range(max_attempts):
        print(f"  Checking status (attempt {attempt + 1}/{max_attempts})...")

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            result = response.json()
            status = result.get('status', 'unknown')
            print(f"  Status: {status}")

            if status == 'completed':
                print("\n  Generation complete!")
                print(json.dumps(result, indent=2))
                return result
            elif status == 'failed':
                print(f"\n  Generation failed: {result.get('error', 'Unknown error')}")
                return result
            # Still processing, wait and retry
        else:
            print(f"  Poll error: {response.status_code}")

        time.sleep(delay)

    print(f"\n  Timeout after {max_attempts * delay} seconds")
    return {"status": "timeout", "generationId": generation_id}


# Concierge Medicine Business Plan Content
CONCIERGE_MEDICINE_CONTENT = """
IMPORTANT: Replace ALL content in the template with this Concierge Medicine Business Plan. Do NOT keep any UCLA Health or Cell & Gene Therapy content. Use ONLY the information below:

PRESENTATION TITLE: Concierge Medicine Business Plan
SUBTITLE: Personalized Healthcare for the Modern Patient

TEAM:
- Dr. Sarah Chen, MD - Chief Medical Officer (15 years internal medicine)
- Michael Torres - CEO (Healthcare administration background)
- Jennifer Park - COO (Operations expert, former hospital administrator)
- David Kim - CFO (Healthcare finance specialist)

EXECUTIVE SUMMARY:
- Launch a premium concierge medicine practice in Los Angeles
- Target: High-net-worth individuals and busy professionals
- Revenue Model: Annual membership fees ($15,000-$25,000/year)
- Year 1 Target: 150 members, $2.5M revenue
- Year 3 Target: 400 members, $7M revenue
- Key differentiator: 24/7 physician access, same-day appointments, comprehensive preventive care

PROBLEM STATEMENT:
- Average primary care visit: 15 minutes
- Wait times for appointments: 3-4 weeks
- Physician burnout leading to rushed care
- Patients feel like numbers, not individuals
- Fragmented care coordination
- Reactive rather than preventive healthcare

BACKGROUND/MARKET CONTEXT:
- US healthcare spending: $4.3 trillion annually
- Concierge medicine market: $6.8B (2024), growing 8.5% CAGR
- LA County has 10M+ residents, 500K+ households earning >$200K
- Only 12 concierge practices currently serving this market
- Post-COVID demand for personalized healthcare surged 40%

SOLUTION:
- Membership-based primary care practice
- Maximum 300 patients per physician (vs. 2,500 traditional)
- Same-day/next-day appointments guaranteed
- 24/7 direct physician access via phone/text
- Annual comprehensive health assessments
- Care coordination with specialists
- Executive health programs for corporate clients

FINANCIAL PROJECTIONS:
Year 1:
- Members: 150
- Revenue: $2.5M
- Operating Costs: $1.8M
- Net Income: $700K

Year 2:
- Members: 275
- Revenue: $4.5M
- Operating Costs: $2.8M
- Net Income: $1.7M

Year 3:
- Members: 400
- Revenue: $7M
- Operating Costs: $4M
- Net Income: $3M

REVENUE MODEL:
- Individual Membership: $18,000/year (avg)
- Family Membership: $30,000/year
- Corporate Executive Program: $25,000/year per executive
- Additional services: Aesthetic medicine, wellness coaching (+15% revenue)

SUCCESS METRICS/KPIs:
- Member retention rate: >95%
- Patient satisfaction (NPS): >80
- Same-day appointment rate: 100%
- Average response time: <30 minutes
- Annual health assessment completion: 100%
- Revenue per member: $18,000+

MARKET SIZE:
- TAM (Total Addressable Market): $15B - All affluent households in US seeking premium healthcare
- SAM (Serviceable Addressable Market): $2B - LA metro area high-net-worth individuals
- SOM (Serviceable Obtainable Market): $50M - Realistic 5-year capture (2,500 members)

COMPETITIVE ANALYSIS:
| Competitor | Price | Patients/Doc | 24/7 Access | Our Advantage |
|------------|-------|--------------|-------------|---------------|
| MDVIP | $1,800/yr | 600 | No | More personalized |
| One Medical | $199/yr | 1,000+ | Limited | True concierge |
| Traditional PCP | Insurance | 2,500 | No | Premium experience |
| Our Practice | $18,000/yr | 300 | Yes | Best-in-class |

GO-TO-MARKET STRATEGY:
Phase 1 (Months 1-6): Foundation
- Secure location in Beverly Hills/West LA
- Hire 2 physicians, support staff
- Launch with 50 founding members at $15K (discounted)

Phase 2 (Months 7-12): Growth
- Corporate partnerships (law firms, tech companies)
- Referral program (1 month free for referrals)
- PR campaign targeting affluent demographics

Phase 3 (Year 2+): Expansion
- Add third physician
- Launch wellness/aesthetic services
- Explore second location

RECOMMENDATION:
Proceed with launch. The LA market is underserved for premium concierge medicine.
- Strong unit economics: 75% gross margin
- Clear product-market fit: Waiting list demand validated
- Experienced team with healthcare expertise
- Low initial capital requirement ($500K)

RISK ANALYSIS:
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Slow member acquisition | Medium | High | Pre-launch marketing, founding member discounts |
| Physician burnout | Low | High | Strict patient caps, support staff |
| Economic downturn | Medium | Medium | Diversify to corporate clients |
| Regulatory changes | Low | Medium | Compliance officer, legal counsel |
| Competition | Medium | Medium | Focus on service differentiation |

IMPLEMENTATION TIMELINE:
Month 1-2: Legal setup, location scouting
Month 3-4: Build-out, equipment, hiring
Month 5: Soft launch (25 founding members)
Month 6: Official launch
Month 7-12: Scale to 150 members
Year 2: Expand to 275 members, add services
Year 3: 400 members, evaluate second location

RESOURCE REQUIREMENTS:
Team:
- 2 Physicians (Year 1), 3 (Year 2)
- 1 Practice Manager
- 2 Medical Assistants
- 1 Patient Coordinator
- 1 Marketing/BD (part-time)

Facility:
- 3,000 sq ft medical office
- Premium waiting area
- 4 exam rooms
- Procedure room

COST ANALYSIS:
Startup Costs: $500,000
- Leasehold improvements: $150,000
- Medical equipment: $100,000
- Technology/EMR: $50,000
- Marketing: $75,000
- Working capital: $125,000

Annual Operating Costs (Year 1): $1.8M
- Physician salaries: $800,000
- Staff salaries: $300,000
- Rent: $180,000
- Insurance: $150,000
- Marketing: $100,000
- Technology: $50,000
- Other: $220,000

ROI PROJECTIONS:
- Break-even: Month 8
- Year 1 ROI: 140%
- Year 3 ROI: 600%
- 5-Year NPV: $8.5M
- Payback period: 10 months

NEXT STEPS:
1. Finalize legal entity formation (Week 1-2)
2. Secure $500K seed funding (Week 2-4)
3. Sign lease for Beverly Hills location (Week 4-6)
4. Begin physician recruitment (Week 4-8)
5. Launch founding member campaign (Week 8)
6. Soft launch with 25 members (Month 5)

CONTACT:
Michael Torres, CEO
conciergemedicine@example.com
(310) 555-0100

Thank you for your consideration. We look forward to revolutionizing primary care in Los Angeles.
"""


if __name__ == "__main__":
    print("=" * 60)
    print("GAMMA PRESENTATION GENERATOR")
    print("=" * 60)
    print("\nGenerating Concierge Medicine Business Plan presentation...")
    print("Using template from your BEAT x UCLA presentation\n")

    # Generate presentation (without export first to see the result)
    result = generate_presentation(CONCIERGE_MEDICINE_CONTENT)

    if result:
        print("\n" + "=" * 60)
        print("PRESENTATION CREATED SUCCESSFULLY!")
        print("=" * 60)

        if 'url' in result:
            print(f"\nView your presentation at: {result['url']}")

        if 'id' in result:
            print(f"Gamma ID: {result['id']}")

        # Optionally generate PPTX export
        print("\n\nWould you like to export as PPTX? Run:")
        print("  generate_presentation(CONCIERGE_MEDICINE_CONTENT, export_format='pptx')")
