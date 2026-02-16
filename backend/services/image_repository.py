"""
Image Repository Service
Provides curated, high-quality images for website generation.

Uses Unsplash CDN for reliable, fast image delivery.
Images are categorized by research topic, hero backgrounds, and team avatars.
"""

import hashlib
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# =============================================================================
# CURATED IMAGE COLLECTIONS
# =============================================================================

# High-quality Unsplash images for research topics
# Format: keyword -> (image_url, credit)
RESEARCH_IMAGES = {
    # Genomics & DNA
    "genomics": (
        "https://images.unsplash.com/photo-1628595351029-c2bf17511435?w=800&q=80",
        "National Cancer Institute"
    ),
    "dna": (
        "https://images.unsplash.com/photo-1614935151651-0bea6508db6b?w=800&q=80",
        "Warren Umoh"
    ),
    "genetics": (
        "https://images.unsplash.com/photo-1579154204601-01588f351e67?w=800&q=80",
        "National Cancer Institute"
    ),
    "sequencing": (
        "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=800&q=80",
        "National Cancer Institute"
    ),

    # Bioinformatics & Computing
    "bioinformatics": (
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&q=80",
        "Markus Spiske"
    ),
    "computational": (
        "https://images.unsplash.com/photo-1504639725590-34d0984388bd?w=800&q=80",
        "Kevin Ku"
    ),
    "data": (
        "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&q=80",
        "Luke Chesser"
    ),
    "algorithm": (
        "https://images.unsplash.com/photo-1555949963-aa79dcee981c?w=800&q=80",
        "Chris Ried"
    ),

    # Machine Learning & AI
    "machine learning": (
        "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&q=80",
        "Steve Johnson"
    ),
    "artificial intelligence": (
        "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&q=80",
        "Andrea De Santis"
    ),
    "neural": (
        "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&q=80",
        "Alina Grubnyak"
    ),
    "deep learning": (
        "https://images.unsplash.com/photo-1509228468518-180dd4864904?w=800&q=80",
        "Pietro Jeng"
    ),

    # Epigenetics & Methylation
    "epigenetics": (
        "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=800&q=80",
        "National Cancer Institute"
    ),
    "methylation": (
        "https://images.unsplash.com/photo-1530026405186-ed1f139313f8?w=800&q=80",
        "National Cancer Institute"
    ),
    "chromatin": (
        "https://images.unsplash.com/photo-1578496479914-7ef3b0193be3?w=800&q=80",
        "National Cancer Institute"
    ),

    # Transcriptomics & RNA
    "transcriptomics": (
        "https://images.unsplash.com/photo-1631049035634-c0d8e987e6b9?w=800&q=80",
        "National Cancer Institute"
    ),
    "rna": (
        "https://images.unsplash.com/photo-1631049552057-403cdb8f0658?w=800&q=80",
        "National Cancer Institute"
    ),
    "expression": (
        "https://images.unsplash.com/photo-1582719471384-894fbb16e074?w=800&q=80",
        "CDC"
    ),

    # Systems Biology & Networks
    "systems biology": (
        "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80",
        "NASA"
    ),
    "network": (
        "https://images.unsplash.com/photo-1545987796-200677ee1011?w=800&q=80",
        "NASA"
    ),
    "pathway": (
        "https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=800&q=80",
        "Hal Gatewood"
    ),

    # Microscopy & Cells
    "microscopy": (
        "https://images.unsplash.com/photo-1516541196182-6bdb0516ed27?w=800&q=80",
        "Michael Longmire"
    ),
    "cell": (
        "https://images.unsplash.com/photo-1530026186672-2cd00ffc50fe?w=800&q=80",
        "National Cancer Institute"
    ),
    "biology": (
        "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=800&q=80",
        "National Cancer Institute"
    ),

    # Proteins & Biochemistry
    "protein": (
        "https://images.unsplash.com/photo-1628595351029-c2bf17511435?w=800&q=80",
        "National Cancer Institute"
    ),
    "biochemistry": (
        "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=800&q=80",
        "National Cancer Institute"
    ),
    "molecular": (
        "https://images.unsplash.com/photo-1614935151651-0bea6508db6b?w=800&q=80",
        "Warren Umoh"
    ),

    # Evolution & Comparative
    "evolution": (
        "https://images.unsplash.com/photo-1557800636-894a64c1696f?w=800&q=80",
        "Jeremy Bishop"
    ),
    "comparative": (
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=800&q=80",
        "Hal Gatewood"
    ),
    "phylogenetic": (
        "https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&q=80",
        "Alexandre Debiève"
    ),

    # Default/Generic Science
    "default": (
        "https://images.unsplash.com/photo-1532094349884-543bc11b234d?w=800&q=80",
        "Hans Reniers"
    ),
    "research": (
        "https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=800&q=80",
        "Hal Gatewood"
    ),
    "science": (
        "https://images.unsplash.com/photo-1564325724739-bae0bd08f787?w=800&q=80",
        "CDC"
    ),
}

# Hero background images - stunning lab/science visuals
HERO_IMAGES = [
    {
        "id": "lab_modern",
        "url": "https://images.unsplash.com/photo-1582719471384-894fbb16e074?w=1920&q=80",
        "credit": "CDC",
        "style": "modern"
    },
    {
        "id": "lab_blue",
        "url": "https://images.unsplash.com/photo-1576086213369-97a306d36557?w=1920&q=80",
        "credit": "National Cancer Institute",
        "style": "blue"
    },
    {
        "id": "dna_abstract",
        "url": "https://images.unsplash.com/photo-1614935151651-0bea6508db6b?w=1920&q=80",
        "credit": "Warren Umoh",
        "style": "abstract"
    },
    {
        "id": "data_science",
        "url": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1920&q=80",
        "credit": "NASA",
        "style": "tech"
    },
    {
        "id": "microscope",
        "url": "https://images.unsplash.com/photo-1516541196182-6bdb0516ed27?w=1920&q=80",
        "credit": "Michael Longmire",
        "style": "classic"
    },
    {
        "id": "neural_network",
        "url": "https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=1920&q=80",
        "credit": "Alina Grubnyak",
        "style": "ai"
    },
    {
        "id": "research_abstract",
        "url": "https://images.unsplash.com/photo-1507413245164-6160d8298b31?w=1920&q=80",
        "credit": "Hal Gatewood",
        "style": "abstract"
    },
    {
        "id": "lab_equipment",
        "url": "https://images.unsplash.com/photo-1532187863486-abf9dbad1b69?w=1920&q=80",
        "credit": "National Cancer Institute",
        "style": "classic"
    },
]

# Notion-style illustrated avatars (using DiceBear API for consistent illustrations)
# DiceBear provides free, consistent avatar generation
AVATAR_STYLES = {
    "notionists": "https://api.dicebear.com/7.x/notionists/svg",
    "lorelei": "https://api.dicebear.com/7.x/lorelei/svg",
    "avataaars": "https://api.dicebear.com/7.x/avataaars/svg",
    "personas": "https://api.dicebear.com/7.x/personas/svg",
    "micah": "https://api.dicebear.com/7.x/micah/svg",
}

# Color palettes for themes
THEME_COLORS = {
    "blue": {
        "primary": "#1e3a5f",
        "secondary": "#3498db",
        "accent": "#2980b9",
        "background": "#f8fafc",
        "text": "#1e293b",
        "text_light": "#64748b",
        "card_bg": "#ffffff",
        "card_text": "#1e293b",
        "hero_overlay": "rgba(30, 58, 95, 0.85)"
    },
    "green": {
        "primary": "#065f46",
        "secondary": "#10b981",
        "accent": "#059669",
        "background": "#f0fdf4",
        "text": "#1e293b",
        "text_light": "#64748b",
        "card_bg": "#ffffff",
        "card_text": "#1e293b",
        "hero_overlay": "rgba(6, 95, 70, 0.85)"
    },
    "purple": {
        "primary": "#5b21b6",
        "secondary": "#8b5cf6",
        "accent": "#7c3aed",
        "background": "#faf5ff",
        "text": "#1e293b",
        "text_light": "#64748b",
        "card_bg": "#ffffff",
        "card_text": "#1e293b",
        "hero_overlay": "rgba(91, 33, 182, 0.85)"
    },
    "dark": {
        "primary": "#0f172a",
        "secondary": "#3b82f6",
        "accent": "#60a5fa",
        "background": "#1e293b",
        "text": "#f8fafc",
        "text_light": "#94a3b8",
        "card_bg": "#334155",
        "card_text": "#f8fafc",
        "hero_overlay": "rgba(15, 23, 42, 0.9)"
    },
    "minimal": {
        "primary": "#18181b",
        "secondary": "#71717a",
        "accent": "#3f3f46",
        "background": "#ffffff",
        "text": "#18181b",
        "text_light": "#71717a",
        "card_bg": "#f4f4f5",
        "card_text": "#18181b",
        "hero_overlay": "rgba(24, 24, 27, 0.8)"
    }
}

# Research area icons (Lucide/Heroicons style SVG paths)
RESEARCH_ICONS = {
    "genomics": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2v20M8 6c4 0 4 4 0 4s0 4 4 4 4 4 0 4M16 6c-4 0-4 4 0 4s0 4-4 4-4 4 0 4"/>
    </svg>''',
    "bioinformatics": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <path d="M8 21h8M12 17v4M6 8h.01M6 12h.01M10 8h8M10 12h8"/>
    </svg>''',
    "machine_learning": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <circle cx="4" cy="6" r="2"/>
        <circle cx="20" cy="6" r="2"/>
        <circle cx="4" cy="18" r="2"/>
        <circle cx="20" cy="18" r="2"/>
        <path d="M9 10L6 7M15 10l3-3M9 14l-3 3M15 14l3 3"/>
    </svg>''',
    "epigenetics": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <path d="M12 6v6l4 2"/>
        <circle cx="12" cy="12" r="3"/>
    </svg>''',
    "transcriptomics": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M4 19V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14"/>
        <path d="M4 19h16"/>
        <path d="M8 7h8M8 11h8M8 15h4"/>
    </svg>''',
    "systems_biology": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="6" cy="6" r="3"/>
        <circle cx="18" cy="6" r="3"/>
        <circle cx="6" cy="18" r="3"/>
        <circle cx="18" cy="18" r="3"/>
        <circle cx="12" cy="12" r="3"/>
        <path d="M8.5 8.5l2 2M13.5 13.5l2 2M8.5 15.5l2-2M13.5 10.5l2-2"/>
    </svg>''',
    "microscopy": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="8" r="5"/>
        <path d="M12 13v8"/>
        <path d="M8 21h8"/>
        <path d="M15.5 5.5l3-3M18.5 2.5l-1 1"/>
    </svg>''',
    "protein": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <ellipse cx="12" cy="5" rx="9" ry="3"/>
        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
        <path d="M3 12c0 1.66 4 3 9 3s9-1.34 9-3"/>
    </svg>''',
    "evolution": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M2 12h4l3-9 4 18 3-9h6"/>
    </svg>''',
    "default": '''<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/>
    </svg>''',
}


@dataclass
class ImageMatch:
    """Result of image matching"""
    url: str
    credit: str
    keyword: str
    confidence: float


class ImageRepository:
    """
    Service for matching content to appropriate images.

    Usage:
        repo = ImageRepository()
        image = repo.get_research_image("genomics and bioinformatics")
        avatar = repo.get_avatar("John Smith")
        hero = repo.get_hero_image("modern")
    """

    def __init__(self, avatar_style: str = "notionists"):
        """
        Initialize the image repository.

        Args:
            avatar_style: DiceBear style for avatars (notionists, lorelei, etc.)
        """
        self.avatar_style = avatar_style
        if avatar_style not in AVATAR_STYLES:
            self.avatar_style = "notionists"

    def get_research_image(self, text: str) -> ImageMatch:
        """
        Find the best matching research image for given text.

        Args:
            text: Research area description or keywords

        Returns:
            ImageMatch with URL, credit, and confidence
        """
        text_lower = text.lower()

        # Try to find exact or partial matches
        best_match = None
        best_score = 0

        for keyword, (url, credit) in RESEARCH_IMAGES.items():
            if keyword == "default":
                continue

            # Check for keyword in text
            if keyword in text_lower:
                score = len(keyword) / len(text_lower) + 0.5  # Bonus for match
                if score > best_score:
                    best_score = score
                    best_match = ImageMatch(url=url, credit=credit, keyword=keyword, confidence=min(score, 1.0))

            # Check for partial word matches
            for word in keyword.split():
                if word in text_lower and len(word) > 3:
                    score = len(word) / len(text_lower) + 0.3
                    if score > best_score:
                        best_score = score
                        best_match = ImageMatch(url=url, credit=credit, keyword=keyword, confidence=min(score, 1.0))

        # Return best match or default
        if best_match:
            return best_match

        url, credit = RESEARCH_IMAGES["default"]
        return ImageMatch(url=url, credit=credit, keyword="default", confidence=0.0)

    def get_research_images_batch(self, areas: List[str]) -> List[ImageMatch]:
        """Get images for multiple research areas, avoiding duplicates."""
        used_urls = set()
        results = []

        for area in areas:
            match = self.get_research_image(area)

            # Avoid duplicate images
            attempts = 0
            while match.url in used_urls and attempts < 5:
                # Try to find alternative
                for keyword, (url, credit) in RESEARCH_IMAGES.items():
                    if url not in used_urls and keyword != "default":
                        match = ImageMatch(url=url, credit=credit, keyword=keyword, confidence=0.3)
                        break
                attempts += 1

            used_urls.add(match.url)
            results.append(match)

        return results

    def get_avatar(self, name: str, seed: Optional[str] = None) -> str:
        """
        Generate a Notion-style avatar URL for a person.

        Args:
            name: Person's name
            seed: Optional seed for consistent avatar generation

        Returns:
            DiceBear avatar URL
        """
        # Use name as seed for consistency
        avatar_seed = seed or name.lower().replace(" ", "-")

        # Generate deterministic but varied avatar
        base_url = AVATAR_STYLES.get(self.avatar_style, AVATAR_STYLES["notionists"])

        return f"{base_url}?seed={avatar_seed}&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf"

    def get_avatar_batch(self, names: List[str]) -> List[Tuple[str, str]]:
        """
        Generate avatars for a list of names.

        Returns:
            List of (name, avatar_url) tuples
        """
        return [(name, self.get_avatar(name)) for name in names]

    def get_hero_image(self, style: Optional[str] = None) -> Dict:
        """
        Get a hero background image.

        Args:
            style: Preferred style (modern, blue, abstract, tech, classic, ai)

        Returns:
            Hero image dict with url, credit, style
        """
        if style:
            style_lower = style.lower()
            for hero in HERO_IMAGES:
                if hero["style"] == style_lower:
                    return hero

        # Return random hero if no style match
        return random.choice(HERO_IMAGES)

    def get_hero_for_keywords(self, keywords: List[str]) -> Dict:
        """
        Select hero image based on research keywords.
        """
        keywords_lower = " ".join(keywords).lower()

        # Match keywords to hero styles
        if any(word in keywords_lower for word in ["ai", "machine", "neural", "deep"]):
            return self.get_hero_image("ai")
        elif any(word in keywords_lower for word in ["data", "computational", "algorithm"]):
            return self.get_hero_image("tech")
        elif any(word in keywords_lower for word in ["dna", "genome", "genetic"]):
            return self.get_hero_image("abstract")
        elif any(word in keywords_lower for word in ["cell", "microscop", "lab"]):
            return self.get_hero_image("classic")
        else:
            return self.get_hero_image("modern")

    def get_theme_colors(self, theme: str = "blue") -> Dict[str, str]:
        """
        Get color palette for a theme.

        Args:
            theme: Theme name (blue, green, purple, dark, minimal)

        Returns:
            Dict with color values
        """
        return THEME_COLORS.get(theme, THEME_COLORS["blue"])

    def get_research_icon(self, area: str) -> str:
        """
        Get SVG icon for a research area.

        Args:
            area: Research area text

        Returns:
            SVG string
        """
        area_lower = area.lower()

        for keyword, icon in RESEARCH_ICONS.items():
            if keyword in area_lower:
                return icon

        return RESEARCH_ICONS["default"]

    def get_gradient_avatar(self, name: str) -> Dict[str, str]:
        """
        Generate a stylish gradient avatar with initials.
        Alternative to illustrated avatars.

        Returns:
            Dict with initials, gradient colors
        """
        # Get initials
        parts = name.split()
        initials = "".join(p[0].upper() for p in parts[:2]) if parts else "?"

        # Generate consistent colors based on name hash
        name_hash = int(hashlib.md5(name.encode()).hexdigest()[:8], 16)

        # Curated gradient pairs
        gradients = [
            ("#667eea", "#764ba2"),  # Purple-violet
            ("#f093fb", "#f5576c"),  # Pink-red
            ("#4facfe", "#00f2fe"),  # Blue-cyan
            ("#43e97b", "#38f9d7"),  # Green-teal
            ("#fa709a", "#fee140"),  # Pink-yellow
            ("#30cfd0", "#330867"),  # Cyan-purple
            ("#a8edea", "#fed6e3"),  # Soft teal-pink
            ("#ff9a9e", "#fecfef"),  # Soft red-pink
            ("#ffecd2", "#fcb69f"),  # Peach
            ("#a1c4fd", "#c2e9fb"),  # Soft blue
        ]

        color1, color2 = gradients[name_hash % len(gradients)]

        return {
            "initials": initials,
            "color1": color1,
            "color2": color2,
            "gradient": f"linear-gradient(135deg, {color1} 0%, {color2} 100%)"
        }


# Convenience function
def get_image_repository(avatar_style: str = "notionists") -> ImageRepository:
    """Factory function to get an image repository instance."""
    return ImageRepository(avatar_style=avatar_style)
