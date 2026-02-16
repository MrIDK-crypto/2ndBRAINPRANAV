"""
Website Template Engine
Generates professional lab websites using pre-designed templates.

Supports multiple themes and layouts with data injection.
"""

import html
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

from services.image_repository import (
    ImageRepository,
    get_image_repository,
    THEME_COLORS,
    RESEARCH_ICONS
)


@dataclass
class WebsiteData:
    """Data structure for website generation"""
    lab_name: str
    tagline: str = ""
    description: str = ""
    research_areas: List[Dict[str, str]] = field(default_factory=list)
    team_members: List[Dict[str, str]] = field(default_factory=list)
    publications: List[Dict[str, str]] = field(default_factory=list)
    projects: List[Dict[str, str]] = field(default_factory=list)
    news_updates: List[Dict[str, str]] = field(default_factory=list)
    contact_info: Dict[str, str] = field(default_factory=dict)
    funding_sources: List[str] = field(default_factory=list)
    collaborators: List[str] = field(default_factory=list)
    institution: str = ""
    institution_url: str = ""


@dataclass
class WebsiteConfig:
    """Configuration for website generation"""
    theme: str = "blue"
    avatar_style: str = "notionists"
    hero_style: str = "modern"
    show_hero_image: bool = True
    include_sections: List[str] = field(default_factory=lambda: [
        "hero", "about", "research", "team", "publications", "projects", "news", "contact"
    ])


class WebsiteTemplateEngine:
    """
    Engine for generating websites from templates.

    Usage:
        data = WebsiteData(lab_name="Smith Lab", ...)
        config = WebsiteConfig(theme="blue")
        engine = WebsiteTemplateEngine(data, config)
        html = engine.generate()
    """

    def __init__(self, data: WebsiteData, config: Optional[WebsiteConfig] = None):
        self.data = data
        self.config = config or WebsiteConfig()
        self.image_repo = get_image_repository(self.config.avatar_style)
        self.colors = self.image_repo.get_theme_colors(self.config.theme)

    def _escape(self, text: str) -> str:
        """Escape HTML entities."""
        return html.escape(str(text)) if text else ""

    def _get_hero_image(self) -> Dict:
        """Get appropriate hero image based on research areas."""
        keywords = [area.get("name", "") for area in self.data.research_areas[:5]]
        return self.image_repo.get_hero_for_keywords(keywords)

    def generate(self) -> str:
        """Generate complete HTML website."""
        hero_image = self._get_hero_image()

        # Generate each section
        sections_html = []

        if "hero" in self.config.include_sections:
            sections_html.append(self._generate_hero(hero_image))

        if "about" in self.config.include_sections:
            sections_html.append(self._generate_about())

        if "research" in self.config.include_sections and self.data.research_areas:
            sections_html.append(self._generate_research())

        if "team" in self.config.include_sections and self.data.team_members:
            sections_html.append(self._generate_team())

        if "publications" in self.config.include_sections and self.data.publications:
            sections_html.append(self._generate_publications())

        if "projects" in self.config.include_sections and self.data.projects:
            sections_html.append(self._generate_projects())

        if "news" in self.config.include_sections and self.data.news_updates:
            sections_html.append(self._generate_news())

        if "contact" in self.config.include_sections:
            sections_html.append(self._generate_contact())

        # Combine with base template
        return self._generate_base(
            body_content="\n".join(sections_html),
            hero_image=hero_image
        )

    def _generate_base(self, body_content: str, hero_image: Dict) -> str:
        """Generate the base HTML template with all CSS and JS."""
        c = self.colors
        lab_name = self._escape(self.data.lab_name)
        institution = self._escape(self.data.institution) if self.data.institution else ""

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="{self._escape(self.data.description[:160]) if self.data.description else lab_name + ' - Research Laboratory'}">
    <title>{lab_name}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        {self._generate_css()}
    </style>
</head>
<body>
    {self._generate_nav()}

    <main>
        {body_content}
    </main>

    {self._generate_footer()}

    <button id="backToTop" aria-label="Back to top">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 15l-6-6-6 6"/>
        </svg>
    </button>

    <script>
        {self._generate_js()}
    </script>
</body>
</html>'''

    def _generate_css(self) -> str:
        """Generate all CSS styles."""
        c = self.colors
        return f'''
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        :root {{
            --primary: {c["primary"]};
            --secondary: {c["secondary"]};
            --accent: {c["accent"]};
            --background: {c["background"]};
            --text: {c["text"]};
            --text-light: {c["text_light"]};
            --card-bg: {c.get("card_bg", "#ffffff")};
            --card-text: {c.get("card_text", c["text"])};
            --hero-overlay: {c["hero_overlay"]};
        }}

        html {{
            scroll-behavior: smooth;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--background);
            color: var(--text);
            line-height: 1.6;
        }}

        /* Navigation */
        .nav {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            z-index: 1000;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }}

        .nav.scrolled {{
            background: rgba(255, 255, 255, 0.98);
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }}

        .nav-container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 70px;
        }}

        .nav-logo {{
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: var(--primary);
            font-weight: 700;
            font-size: 1.25rem;
        }}

        .nav-logo .badge {{
            background: var(--primary);
            color: white;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
        }}

        .nav-links {{
            display: flex;
            align-items: center;
            gap: 32px;
        }}

        .nav-links a {{
            text-decoration: none;
            color: var(--text-light);
            font-weight: 500;
            font-size: 0.9rem;
            transition: color 0.2s;
            position: relative;
        }}

        .nav-links a:hover, .nav-links a.active {{
            color: var(--primary);
        }}

        .nav-links a::after {{
            content: '';
            position: absolute;
            bottom: -4px;
            left: 0;
            width: 0;
            height: 2px;
            background: var(--secondary);
            transition: width 0.2s;
        }}

        .nav-links a:hover::after, .nav-links a.active::after {{
            width: 100%;
        }}

        .mobile-menu-btn {{
            display: none;
            background: none;
            border: none;
            cursor: pointer;
            padding: 8px;
        }}

        /* Hero Section */
        .hero {{
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}

        .hero-bg {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}

        .hero-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: var(--hero-overlay);
        }}

        .hero-content {{
            position: relative;
            z-index: 10;
            text-align: center;
            color: white;
            padding: 40px;
            max-width: 900px;
        }}

        .hero h1 {{
            font-size: clamp(2.5rem, 6vw, 4rem);
            font-weight: 800;
            margin-bottom: 24px;
            line-height: 1.1;
        }}

        .hero .tagline {{
            font-size: clamp(1.1rem, 2.5vw, 1.5rem);
            opacity: 0.9;
            margin-bottom: 40px;
            font-weight: 300;
        }}

        .hero-buttons {{
            display: flex;
            gap: 16px;
            justify-content: center;
            flex-wrap: wrap;
        }}

        .btn {{
            padding: 14px 32px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 1rem;
            text-decoration: none;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }}

        .btn-primary {{
            background: white;
            color: var(--primary);
        }}

        .btn-primary:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}

        .btn-secondary {{
            background: transparent;
            color: white;
            border: 2px solid rgba(255,255,255,0.5);
        }}

        .btn-secondary:hover {{
            background: rgba(255,255,255,0.1);
            border-color: white;
        }}

        /* Section Styles */
        section {{
            padding: 100px 24px;
        }}

        .section-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .section-header {{
            text-align: center;
            margin-bottom: 60px;
        }}

        .section-header h2 {{
            font-size: 2.5rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 16px;
        }}

        .section-header p {{
            color: var(--text-light);
            font-size: 1.1rem;
            max-width: 600px;
            margin: 0 auto;
        }}

        /* About Section */
        .about-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 60px;
            align-items: center;
        }}

        .about-text {{
            font-size: 1.1rem;
            line-height: 1.8;
        }}

        .about-text p {{
            margin-bottom: 20px;
        }}

        .about-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 24px;
        }}

        .stat-card {{
            background: var(--card-bg);
            padding: 30px;
            border-radius: 16px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }}

        .stat-card:hover {{
            transform: translateY(-4px);
        }}

        .stat-number {{
            font-size: 3rem;
            font-weight: 800;
            color: var(--secondary);
            line-height: 1;
        }}

        .stat-label {{
            color: var(--text-light);
            margin-top: 8px;
            font-weight: 500;
        }}

        /* Research Section */
        .research-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }}

        .research-card {{
            background: var(--card-bg);
            border-radius: 16px;
            overflow: hidden;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            transition: transform 0.3s, box-shadow 0.3s;
        }}

        .research-card:hover {{
            transform: translateY(-8px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}

        .research-card-image {{
            height: 200px;
            background-size: cover;
            background-position: center;
            position: relative;
        }}

        .research-card-image::after {{
            content: '';
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 100px;
            background: linear-gradient(transparent, rgba(0,0,0,0.5));
        }}

        .research-card-icon {{
            position: absolute;
            bottom: 16px;
            left: 16px;
            width: 50px;
            height: 50px;
            background: white;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 1;
            color: var(--primary);
        }}

        .research-card-link {{
            display: block;
            text-decoration: none;
            color: inherit;
        }}

        .research-card-content {{
            padding: 24px;
        }}

        .research-card h3 {{
            font-size: 1.25rem;
            font-weight: 600;
            margin-bottom: 12px;
            color: var(--primary);
            transition: color 0.2s;
        }}

        .research-card-link:hover h3 {{
            color: var(--secondary);
        }}

        .research-card p {{
            color: var(--text-light);
            font-size: 0.95rem;
            line-height: 1.6;
        }}

        /* Team Section */
        .team-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 30px;
        }}

        .team-card {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            transition: transform 0.3s;
        }}

        .team-card:hover {{
            transform: translateY(-4px);
        }}

        .team-avatar {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            margin: 0 auto 20px;
            overflow: hidden;
            border: 4px solid var(--background);
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}

        .team-avatar img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .team-card h3 {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 4px;
            color: var(--card-text);
        }}

        .team-role {{
            color: var(--secondary);
            font-weight: 500;
            font-size: 0.9rem;
            margin-bottom: 12px;
        }}

        .team-bio {{
            color: var(--text-light);
            font-size: 0.9rem;
            margin-bottom: 16px;
        }}

        .team-email {{
            color: var(--text-light);
            font-size: 0.85rem;
            text-decoration: none;
        }}

        .team-email:hover {{
            color: var(--secondary);
        }}

        /* Publications Section */
        .publications-search {{
            max-width: 500px;
            margin: 0 auto 40px;
            position: relative;
        }}

        .publications-search input {{
            width: 100%;
            padding: 16px 24px 16px 50px;
            border: 2px solid #e5e7eb;
            border-radius: 12px;
            font-size: 1rem;
            transition: border-color 0.2s;
        }}

        .publications-search input:focus {{
            outline: none;
            border-color: var(--secondary);
        }}

        .publications-search svg {{
            position: absolute;
            left: 18px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-light);
        }}

        .publications-list {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .publication-card {{
            background: var(--card-bg);
            padding: 24px;
            border-radius: 12px;
            border-left: 4px solid var(--secondary);
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: transform 0.2s;
        }}

        .publication-card:hover {{
            transform: translateX(4px);
        }}

        .publication-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--card-text);
            margin-bottom: 8px;
            line-height: 1.4;
        }}

        .publication-title a {{
            color: var(--card-text);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .publication-title a:hover {{
            color: var(--secondary);
            text-decoration: underline;
        }}

        .pub-link-icon {{
            display: inline-block;
            vertical-align: middle;
            margin-left: 6px;
            opacity: 0.6;
        }}

        .publication-title:hover .pub-link-icon {{
            opacity: 1;
            color: var(--secondary);
        }}

        .publication-authors {{
            color: var(--text-light);
            font-size: 0.9rem;
            margin-bottom: 8px;
        }}

        .publication-venue {{
            color: var(--secondary);
            font-size: 0.85rem;
            font-weight: 500;
        }}

        /* Projects Section */
        .projects-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
        }}

        .project-card {{
            background: var(--card-bg);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            position: relative;
            overflow: hidden;
        }}

        .project-status {{
            position: absolute;
            top: 20px;
            right: 20px;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .project-status.ongoing {{
            background: #dcfce7;
            color: #15803d;
        }}

        .project-status.completed {{
            background: #dbeafe;
            color: #1d4ed8;
        }}

        .project-card h3 {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary);
            margin-bottom: 12px;
            padding-right: 80px;
        }}

        .project-card p {{
            color: var(--text-light);
            line-height: 1.6;
        }}

        /* News Section */
        .news-timeline {{
            position: relative;
            max-width: 800px;
            margin: 0 auto;
        }}

        .news-timeline::before {{
            content: '';
            position: absolute;
            left: 20px;
            top: 0;
            bottom: 0;
            width: 2px;
            background: linear-gradient(var(--secondary), var(--primary));
        }}

        .news-item {{
            position: relative;
            padding-left: 60px;
            padding-bottom: 40px;
        }}

        .news-item::before {{
            content: '';
            position: absolute;
            left: 12px;
            top: 5px;
            width: 18px;
            height: 18px;
            background: var(--secondary);
            border-radius: 50%;
            border: 4px solid var(--background);
        }}

        .news-date {{
            color: var(--secondary);
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 8px;
        }}

        .news-item h3 {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text);
        }}

        .news-item p {{
            color: var(--text-light);
        }}

        /* Contact Section */
        .contact-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 60px;
        }}

        .contact-info h3 {{
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 24px;
            color: var(--primary);
        }}

        .contact-item {{
            display: flex;
            align-items: flex-start;
            gap: 16px;
            margin-bottom: 20px;
        }}

        .contact-icon {{
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, var(--secondary), var(--primary));
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            flex-shrink: 0;
        }}

        .contact-item-content {{
            flex: 1;
        }}

        .contact-item-label {{
            font-weight: 600;
            color: var(--text);
            margin-bottom: 4px;
        }}

        .contact-item-value {{
            color: var(--text-light);
        }}

        .contact-item-value a {{
            color: var(--secondary);
            text-decoration: none;
        }}

        .contact-form {{
            background: var(--card-bg);
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        }}

        .form-group {{
            margin-bottom: 20px;
        }}

        .form-group label {{
            display: block;
            font-weight: 500;
            margin-bottom: 8px;
            color: var(--card-text);
        }}

        .form-group input, .form-group textarea {{
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            font-size: 1rem;
            font-family: inherit;
            transition: border-color 0.2s;
        }}

        .form-group input:focus, .form-group textarea:focus {{
            outline: none;
            border-color: var(--secondary);
        }}

        .form-group textarea {{
            min-height: 120px;
            resize: vertical;
        }}

        .form-submit {{
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, var(--secondary), var(--primary));
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .form-submit:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
        }}

        /* Footer */
        .footer {{
            background: var(--primary);
            color: white;
            padding: 60px 24px 30px;
        }}

        .footer-container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        .footer-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr 1fr 1fr;
            gap: 40px;
            margin-bottom: 40px;
        }}

        .footer-brand h3 {{
            font-size: 1.5rem;
            margin-bottom: 16px;
        }}

        .footer-brand p {{
            opacity: 0.8;
            line-height: 1.6;
        }}

        .footer h4 {{
            font-size: 1rem;
            margin-bottom: 20px;
            font-weight: 600;
        }}

        .footer-links {{
            list-style: none;
        }}

        .footer-links li {{
            margin-bottom: 12px;
        }}

        .footer-links a {{
            color: rgba(255,255,255,0.8);
            text-decoration: none;
            transition: color 0.2s;
        }}

        .footer-links a:hover {{
            color: white;
        }}

        .footer-bottom {{
            border-top: 1px solid rgba(255,255,255,0.1);
            padding-top: 24px;
            text-align: center;
            opacity: 0.7;
            font-size: 0.9rem;
        }}

        /* Back to Top Button */
        #backToTop {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 50px;
            height: 50px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 50%;
            cursor: pointer;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            z-index: 999;
        }}

        #backToTop.visible {{
            opacity: 1;
            visibility: visible;
        }}

        #backToTop:hover {{
            transform: translateY(-4px);
        }}

        /* Animations */
        .fade-in {{
            opacity: 0;
            transform: translateY(30px);
            transition: opacity 0.6s ease, transform 0.6s ease;
        }}

        .fade-in.visible {{
            opacity: 1;
            transform: translateY(0);
        }}

        /* Responsive */
        @media (max-width: 1024px) {{
            .about-content {{
                grid-template-columns: 1fr;
                gap: 40px;
            }}

            .contact-grid {{
                grid-template-columns: 1fr;
            }}

            .footer-grid {{
                grid-template-columns: 1fr 1fr;
            }}
        }}

        @media (max-width: 768px) {{
            .nav-links {{
                display: none;
            }}

            .mobile-menu-btn {{
                display: block;
            }}

            .hero h1 {{
                font-size: 2rem;
            }}

            .section-header h2 {{
                font-size: 2rem;
            }}

            .research-grid, .projects-grid {{
                grid-template-columns: 1fr;
            }}

            .footer-grid {{
                grid-template-columns: 1fr;
                text-align: center;
            }}

            .about-stats {{
                grid-template-columns: 1fr 1fr;
            }}
        }}
'''

    def _generate_js(self) -> str:
        """Generate JavaScript for interactivity."""
        return '''
        // Scroll-based navigation background
        const nav = document.querySelector('.nav');
        const backToTop = document.getElementById('backToTop');

        window.addEventListener('scroll', () => {
            if (window.scrollY > 50) {
                nav.classList.add('scrolled');
                backToTop.classList.add('visible');
            } else {
                nav.classList.remove('scrolled');
                backToTop.classList.remove('visible');
            }
        });

        // Back to top button
        backToTop.addEventListener('click', () => {
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });

        // Smooth scroll for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const target = document.querySelector(this.getAttribute('href'));
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            });
        });

        // Active navigation link
        const sections = document.querySelectorAll('section[id]');
        const navLinks = document.querySelectorAll('.nav-links a');

        window.addEventListener('scroll', () => {
            let current = '';
            sections.forEach(section => {
                const sectionTop = section.offsetTop - 100;
                if (window.scrollY >= sectionTop) {
                    current = section.getAttribute('id');
                }
            });

            navLinks.forEach(link => {
                link.classList.remove('active');
                if (link.getAttribute('href') === '#' + current) {
                    link.classList.add('active');
                }
            });
        });

        // Fade in animation on scroll
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        }, observerOptions);

        document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));

        // Publications search
        const searchInput = document.getElementById('pubSearch');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                const query = e.target.value.toLowerCase();
                document.querySelectorAll('.publication-card').forEach(card => {
                    const text = card.textContent.toLowerCase();
                    card.style.display = text.includes(query) ? 'block' : 'none';
                });
            });
        }
'''

    def _generate_nav(self) -> str:
        """Generate navigation bar."""
        lab_name = self._escape(self.data.lab_name)
        institution = self._escape(self.data.institution) if self.data.institution else ""

        nav_links = []
        section_map = {
            "about": ("About", "#about"),
            "research": ("Research", "#research"),
            "team": ("Team", "#team"),
            "publications": ("Publications", "#publications"),
            "projects": ("Projects", "#projects"),
            "news": ("News", "#news"),
            "contact": ("Contact", "#contact"),
        }

        for section_id, (label, href) in section_map.items():
            if section_id in self.config.include_sections:
                # Check if we have data for this section
                should_show = True
                if section_id == "research" and not self.data.research_areas:
                    should_show = False
                elif section_id == "team" and not self.data.team_members:
                    should_show = False
                elif section_id == "publications" and not self.data.publications:
                    should_show = False
                elif section_id == "projects" and not self.data.projects:
                    should_show = False
                elif section_id == "news" and not self.data.news_updates:
                    should_show = False

                if should_show:
                    nav_links.append(f'<a href="{href}">{label}</a>')

        badge_html = f'<span class="badge">{institution}</span>' if institution else ""

        return f'''
    <nav class="nav">
        <div class="nav-container">
            <a href="#" class="nav-logo">
                {lab_name}
                {badge_html}
            </a>
            <div class="nav-links">
                <a href="#" class="active">Home</a>
                {" ".join(nav_links)}
            </div>
            <button class="mobile-menu-btn" aria-label="Menu">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="3" y1="12" x2="21" y2="12"/>
                    <line x1="3" y1="6" x2="21" y2="6"/>
                    <line x1="3" y1="18" x2="21" y2="18"/>
                </svg>
            </button>
        </div>
    </nav>
'''

    def _generate_hero(self, hero_image: Dict) -> str:
        """Generate hero section."""
        lab_name = self._escape(self.data.lab_name)
        tagline = self._escape(self.data.tagline) if self.data.tagline else "Advancing Science Through Innovation"

        bg_style = f'background-image: url("{hero_image["url"]}");' if self.config.show_hero_image else ""

        return f'''
    <section class="hero" id="home">
        <div class="hero-bg" style='{bg_style}'></div>
        <div class="hero-overlay"></div>
        <div class="hero-content">
            <h1>{lab_name}</h1>
            <p class="tagline">{tagline}</p>
            <div class="hero-buttons">
                <a href="#research" class="btn btn-primary">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"/>
                        <path d="M21 21l-4.35-4.35"/>
                    </svg>
                    Explore Research
                </a>
                <a href="#contact" class="btn btn-secondary">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                        <circle cx="8.5" cy="7" r="4"/>
                        <line x1="20" y1="8" x2="20" y2="14"/>
                        <line x1="23" y1="11" x2="17" y2="11"/>
                    </svg>
                    Join Our Team
                </a>
            </div>
        </div>
    </section>
'''

    def _generate_about(self) -> str:
        """Generate about section."""
        description = self._escape(self.data.description) if self.data.description else ""

        # Calculate stats
        team_count = len(self.data.team_members)
        pub_count = len(self.data.publications)
        project_count = len(self.data.projects)
        area_count = len(self.data.research_areas)

        return f'''
    <section id="about">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>About Our Lab</h2>
            </div>
            <div class="about-content">
                <div class="about-text fade-in">
                    <p>{description or "Our laboratory is dedicated to pushing the boundaries of scientific knowledge through innovative research and collaboration."}</p>
                </div>
                <div class="about-stats fade-in">
                    <div class="stat-card">
                        <div class="stat-number">{team_count}</div>
                        <div class="stat-label">Team Members</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{pub_count}</div>
                        <div class="stat-label">Publications</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{project_count}</div>
                        <div class="stat-label">Active Projects</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{area_count}</div>
                        <div class="stat-label">Research Areas</div>
                    </div>
                </div>
            </div>
        </div>
    </section>
'''

    def _generate_research(self) -> str:
        """Generate research areas section."""
        # Get images for each research area
        area_names = [area.get("name", "") for area in self.data.research_areas]
        images = self.image_repo.get_research_images_batch(area_names)

        cards_html = []
        for i, area in enumerate(self.data.research_areas[:6]):  # Limit to 6
            name = self._escape(area.get("name", "Research Area"))
            description = self._escape(area.get("description", ""))
            image = images[i] if i < len(images) else self.image_repo.get_research_image("default")
            icon = self.image_repo.get_research_icon(name)

            # Create a slug for the anchor ID
            slug = "".join(c if c.isalnum() else "-" for c in name.lower()).strip("-")
            area_id = f"research-{slug}"

            cards_html.append(f'''
                <div class="research-card fade-in" id="{area_id}">
                    <a href="#{area_id}" class="research-card-link">
                        <div class="research-card-image" style="background-image: url('{image.url}');">
                            <div class="research-card-icon">{icon}</div>
                        </div>
                        <div class="research-card-content">
                            <h3>{name}</h3>
                            <p>{description or "Exploring cutting-edge approaches in this field."}</p>
                        </div>
                    </a>
                </div>
''')

        return f'''
    <section id="research" style="background: white;">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>Research Areas</h2>
                <p>Our lab focuses on several interconnected areas of research</p>
            </div>
            <div class="research-grid">
                {"".join(cards_html)}
            </div>
        </div>
    </section>
'''

    def _generate_team(self) -> str:
        """Generate team section."""
        cards_html = []
        for member in self.data.team_members[:12]:  # Limit to 12
            name = self._escape(member.get("name", "Team Member"))
            role = self._escape(member.get("role", ""))
            bio = self._escape(member.get("bio", ""))
            email = self._escape(member.get("email", ""))

            # Get avatar
            avatar_url = self.image_repo.get_avatar(name)

            email_html = f'<a href="mailto:{email}" class="team-email">{email}</a>' if email else ""

            cards_html.append(f'''
                <div class="team-card fade-in">
                    <div class="team-avatar">
                        <img src="{avatar_url}" alt="{name}" loading="lazy">
                    </div>
                    <h3>{name}</h3>
                    <div class="team-role">{role}</div>
                    <p class="team-bio">{bio}</p>
                    {email_html}
                </div>
''')

        return f'''
    <section id="team">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>Our Team</h2>
                <p>Meet the researchers driving our discoveries</p>
            </div>
            <div class="team-grid">
                {"".join(cards_html)}
            </div>
        </div>
    </section>
'''

    def _generate_publications(self) -> str:
        """Generate publications section."""
        pubs_html = []
        for pub in self.data.publications[:15]:  # Limit to 15
            title = self._escape(pub.get("title", "Publication"))
            authors = self._escape(pub.get("authors", ""))
            venue = self._escape(pub.get("venue", ""))
            year = self._escape(pub.get("year", ""))
            url = pub.get("url", "")
            doi = pub.get("doi", "")

            venue_text = f"{venue}" if venue else ""
            if year:
                venue_text += f", {year}" if venue_text else year

            # Create link for title if URL or DOI exists
            if url:
                title_html = f'<a href="{self._escape(url)}" target="_blank" rel="noopener">{title}</a>'
            elif doi:
                doi_url = f"https://doi.org/{self._escape(doi)}" if not doi.startswith("http") else self._escape(doi)
                title_html = f'<a href="{doi_url}" target="_blank" rel="noopener">{title}</a>'
            else:
                title_html = title

            # Add link icon if there's a link
            link_icon = ''
            if url or doi:
                link_icon = '''<svg class="pub-link-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                    <polyline points="15 3 21 3 21 9"/>
                    <line x1="10" y1="14" x2="21" y2="3"/>
                </svg>'''

            pubs_html.append(f'''
                <div class="publication-card fade-in">
                    <div class="publication-title">{title_html} {link_icon}</div>
                    <div class="publication-authors">{authors}</div>
                    <div class="publication-venue">{venue_text}</div>
                </div>
''')

        return f'''
    <section id="publications" style="background: white;">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>Publications</h2>
                <p>Selected publications from our research group</p>
            </div>
            <div class="publications-search fade-in">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"/>
                    <path d="M21 21l-4.35-4.35"/>
                </svg>
                <input type="text" id="pubSearch" placeholder="Search publications...">
            </div>
            <div class="publications-list">
                {"".join(pubs_html)}
            </div>
        </div>
    </section>
'''

    def _generate_projects(self) -> str:
        """Generate projects section."""
        projects_html = []
        for project in self.data.projects[:8]:  # Limit to 8
            name = self._escape(project.get("name", "Project"))
            description = self._escape(project.get("description", ""))
            status = project.get("status", "ongoing").lower()

            status_class = "ongoing" if "ongoing" in status or "active" in status else "completed"
            status_label = "Ongoing" if status_class == "ongoing" else "Completed"

            projects_html.append(f'''
                <div class="project-card fade-in">
                    <span class="project-status {status_class}">{status_label}</span>
                    <h3>{name}</h3>
                    <p>{description}</p>
                </div>
''')

        return f'''
    <section id="projects">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>Projects</h2>
                <p>Current and past research initiatives</p>
            </div>
            <div class="projects-grid">
                {"".join(projects_html)}
            </div>
        </div>
    </section>
'''

    def _generate_news(self) -> str:
        """Generate news section."""
        news_html = []
        for news in self.data.news_updates[:5]:  # Limit to 5
            title = self._escape(news.get("title", "Update"))
            date = self._escape(news.get("date", ""))
            summary = self._escape(news.get("summary", ""))

            news_html.append(f'''
                <div class="news-item fade-in">
                    <div class="news-date">{date}</div>
                    <h3>{title}</h3>
                    <p>{summary}</p>
                </div>
''')

        return f'''
    <section id="news" style="background: white;">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>News & Updates</h2>
                <p>Latest happenings from our lab</p>
            </div>
            <div class="news-timeline">
                {"".join(news_html)}
            </div>
        </div>
    </section>
'''

    def _generate_contact(self) -> str:
        """Generate contact section."""
        contact = self.data.contact_info
        email = self._escape(contact.get("email", ""))
        phone = self._escape(contact.get("phone", ""))
        address = self._escape(contact.get("address", ""))
        office = self._escape(contact.get("office", ""))

        # Collaborators
        collaborators_html = ""
        if self.data.collaborators:
            items = "".join(f"<li>{self._escape(c)}</li>" for c in self.data.collaborators[:8])
            collaborators_html = f'''
                <div style="margin-top: 30px;">
                    <h4 style="margin-bottom: 12px; color: var(--text);">Collaborators</h4>
                    <ul style="list-style: none; color: var(--text-light); line-height: 1.8;">
                        {items}
                    </ul>
                </div>
'''

        return f'''
    <section id="contact">
        <div class="section-container">
            <div class="section-header fade-in">
                <h2>Contact & Collaborate</h2>
                <p>Get in touch with our research team</p>
            </div>
            <div class="contact-grid">
                <div class="contact-info fade-in">
                    <h3>Get in Touch</h3>
                    <div class="contact-item">
                        <div class="contact-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                                <polyline points="22,6 12,13 2,6"/>
                            </svg>
                        </div>
                        <div class="contact-item-content">
                            <div class="contact-item-label">Email</div>
                            <div class="contact-item-value"><a href="mailto:{email}">{email or "contact@lab.edu"}</a></div>
                        </div>
                    </div>
                    <div class="contact-item">
                        <div class="contact-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>
                            </svg>
                        </div>
                        <div class="contact-item-content">
                            <div class="contact-item-label">Phone</div>
                            <div class="contact-item-value">{phone or "Contact via email"}</div>
                        </div>
                    </div>
                    <div class="contact-item">
                        <div class="contact-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                                <circle cx="12" cy="10" r="3"/>
                            </svg>
                        </div>
                        <div class="contact-item-content">
                            <div class="contact-item-label">Address</div>
                            <div class="contact-item-value">{address or "University Campus"}</div>
                        </div>
                    </div>
                    <div class="contact-item">
                        <div class="contact-icon">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
                                <polyline points="9 22 9 12 15 12 15 22"/>
                            </svg>
                        </div>
                        <div class="contact-item-content">
                            <div class="contact-item-label">Office</div>
                            <div class="contact-item-value">{office or "By appointment"}</div>
                        </div>
                    </div>
                    {collaborators_html}
                </div>
                <div class="contact-form fade-in">
                    <form action="#" method="POST">
                        <div class="form-group">
                            <label for="name">Name</label>
                            <input type="text" id="name" name="name" placeholder="Your name" required>
                        </div>
                        <div class="form-group">
                            <label for="email">Email</label>
                            <input type="email" id="email" name="email" placeholder="you@example.com" required>
                        </div>
                        <div class="form-group">
                            <label for="message">Message</label>
                            <textarea id="message" name="message" placeholder="Your message..." required></textarea>
                        </div>
                        <button type="submit" class="form-submit">Send Message</button>
                    </form>
                </div>
            </div>
        </div>
    </section>
'''

    def _generate_footer(self) -> str:
        """Generate footer section."""
        lab_name = self._escape(self.data.lab_name)
        institution = self._escape(self.data.institution) if self.data.institution else ""
        year = datetime.now().year

        funding_html = ""
        if self.data.funding_sources:
            items = "".join(f"<li>{self._escape(f)}</li>" for f in self.data.funding_sources[:5])
            funding_html = f'''
                <div>
                    <h4>Funding</h4>
                    <ul class="footer-links">
                        {items}
                    </ul>
                </div>
'''

        return f'''
    <footer class="footer">
        <div class="footer-container">
            <div class="footer-grid">
                <div class="footer-brand">
                    <h3>{lab_name}</h3>
                    <p>{institution}<br>Advancing scientific discovery through innovative research and collaboration.</p>
                </div>
                <div>
                    <h4>Quick Links</h4>
                    <ul class="footer-links">
                        <li><a href="#about">About</a></li>
                        <li><a href="#research">Research</a></li>
                        <li><a href="#team">Team</a></li>
                        <li><a href="#publications">Publications</a></li>
                    </ul>
                </div>
                <div>
                    <h4>Resources</h4>
                    <ul class="footer-links">
                        <li><a href="#projects">Projects</a></li>
                        <li><a href="#news">News</a></li>
                        <li><a href="#contact">Contact</a></li>
                    </ul>
                </div>
                {funding_html}
            </div>
            <div class="footer-bottom">
                <p>&copy; {year} {lab_name}. All rights reserved.</p>
            </div>
        </div>
    </footer>
'''


def generate_website_from_data(data: WebsiteData, config: Optional[WebsiteConfig] = None) -> str:
    """
    Convenience function to generate a website from data.

    Args:
        data: WebsiteData with all lab information
        config: Optional WebsiteConfig for customization

    Returns:
        Complete HTML string
    """
    engine = WebsiteTemplateEngine(data, config)
    return engine.generate()
