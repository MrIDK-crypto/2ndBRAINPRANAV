"""
Website Scraper Connector - Self-hosted BFS Crawler

Uses requests + BeautifulSoup for crawling and content extraction.
Includes OCR for images without alt text via pytesseract.
No external API keys required.

SYNCHRONOUS implementation - works with gevent workers.
"""

import re
import io
import time
import json
import hashlib
import traceback
import xml.etree.ElementTree as ET
from collections import deque
from datetime import datetime
from typing import List, Dict, Optional, Any, Set
from urllib.parse import urlparse, urljoin, urldefrag, parse_qs, urlencode

import requests
from bs4 import BeautifulSoup, Tag

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# html2text for clean HTML -> text conversion
try:
    import html2text
    HTML2TEXT_AVAILABLE = True
except ImportError:
    HTML2TEXT_AVAILABLE = False
    print("[WebScraper] html2text not installed, falling back to BeautifulSoup get_text()")

# pytesseract for image OCR (optional)
OCR_AVAILABLE = False
try:
    import pytesseract
    from PIL import Image
    # Quick check that tesseract binary exists
    pytesseract.get_tesseract_version()
    OCR_AVAILABLE = True
    print("[WebScraper] pytesseract + tesseract available for image OCR")
except Exception as e:
    print(f"[WebScraper] OCR not available (will skip image OCR): {e}")


# Common icon font class -> text label mapping
ICON_MAP = {
    # Font Awesome
    "fa-home": "Home", "fa-search": "Search", "fa-user": "User",
    "fa-envelope": "Email", "fa-phone": "Phone", "fa-lock": "Lock",
    "fa-cog": "Settings", "fa-gear": "Settings", "fa-star": "Star",
    "fa-heart": "Heart", "fa-check": "Check", "fa-times": "Close",
    "fa-plus": "Add", "fa-minus": "Remove", "fa-edit": "Edit",
    "fa-trash": "Delete", "fa-download": "Download", "fa-upload": "Upload",
    "fa-file": "File", "fa-folder": "Folder", "fa-calendar": "Calendar",
    "fa-clock": "Clock", "fa-map-marker": "Location", "fa-bell": "Notification",
    "fa-comment": "Comment", "fa-share": "Share", "fa-link": "Link",
    "fa-globe": "Globe", "fa-info": "Info", "fa-question": "Help",
    "fa-exclamation": "Warning", "fa-arrow-right": "Next", "fa-arrow-left": "Back",
    "fa-chevron-right": "Next", "fa-chevron-left": "Back",
    "fa-chevron-down": "Expand", "fa-chevron-up": "Collapse",
    "fa-bars": "Menu", "fa-external-link": "External Link",
    "fa-github": "GitHub", "fa-twitter": "Twitter", "fa-linkedin": "LinkedIn",
    "fa-facebook": "Facebook", "fa-instagram": "Instagram",
    "fa-youtube": "YouTube", "fa-slack": "Slack",
    # Material Icons (class content text)
    "home": "Home", "search": "Search", "menu": "Menu",
    "close": "Close", "settings": "Settings", "account_circle": "User",
    "email": "Email", "phone": "Phone", "delete": "Delete",
    "edit": "Edit", "add": "Add", "remove": "Remove",
    "check": "Check", "info": "Info", "warning": "Warning",
    "error": "Error", "help": "Help", "star": "Star",
    "favorite": "Favorite", "share": "Share", "download": "Download",
    "upload": "Upload", "notifications": "Notifications",
    "arrow_forward": "Next", "arrow_back": "Back",
}


class WebScraperConnector(BaseConnector):
    """
    Self-hosted website scraper using requests + BeautifulSoup.
    BFS crawl with smart content extraction and optional image OCR.

    SYNCHRONOUS implementation - works with gevent workers.
    """

    CONNECTOR_TYPE = "webscraper"
    REQUIRED_CREDENTIALS = []
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_pages": 50,
        "max_depth": 5,
        "crawl_delay": 0.3,
        "exclude_patterns": [],
        "timeout": 15,
        "priority_paths": [],
    }

    # File extensions to skip entirely (never fetch these URLs)
    SKIP_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".rar", ".7z",
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico",
        ".mp3", ".mp4", ".avi", ".mov", ".wmv", ".flv", ".wav", ".ogg",
        ".exe", ".dmg", ".msi", ".bin", ".iso",
        ".css", ".js", ".json", ".xml", ".csv", ".tsv",
        ".woff", ".woff2", ".ttf", ".eot",
    }

    # Limits
    MAX_PAGE_SIZE = 5 * 1024 * 1024  # 5MB per page
    MAX_OCR_PER_PAGE = 10
    OCR_TIMEOUT = 5  # seconds
    MIN_IMAGE_SIZE = 50  # pixels - skip tiny icons/spacers
    MAX_IMAGE_DOWNLOAD = 2 * 1024 * 1024  # 2MB per image

    # Domain circuit breaker: skip domains after this many consecutive failures
    DOMAIN_FAILURE_THRESHOLD = 3

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        print(f"[WebScraper] __init__ called (self-hosted crawler)")
        super().__init__(config)
        self.tenant_id = tenant_id
        self.error_count = 0
        self.success_count = 0
        # Track consecutive failures per domain for circuit breaker
        self._domain_failures: Dict[str, int] = {}
        self._domain_skipped: Dict[str, int] = {}

        # Set up requests session with real browser User-Agent
        # Many sites (especially university sites) block bot-like UAs or have WAFs
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
        })

        # Per-page fetch timeout. Minimum 20s for server-to-server (cloud hosting has higher latency)
        self.timeout = max(20, int(config.settings.get("timeout", 30)))

        # Set up html2text converter
        self.h2t = None
        if HTML2TEXT_AVAILABLE:
            self.h2t = html2text.HTML2Text()
            self.h2t.ignore_links = False
            self.h2t.ignore_images = False
            self.h2t.ignore_emphasis = False
            self.h2t.body_width = 0  # No line wrapping
            self.h2t.skip_internal_links = True
            self.h2t.inline_links = True

        print(f"[WebScraper] html2text: {HTML2TEXT_AVAILABLE}, OCR: {OCR_AVAILABLE}")

    def _url_to_filename(self, url: str) -> str:
        """Convert URL to safe filename hash"""
        return f"page_{hashlib.sha256(url.encode()).hexdigest()[:16]}"

    # ──────────────────────────────────────────────────────────────
    # URL helpers
    # ──────────────────────────────────────────────────────────────

    # Query params to always strip (tracking, session, sorting — not content)
    STRIP_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "session", "sessionid", "sid",
        "sort", "order", "filter", "view", "lang", "locale",
        "cb", "cache", "timestamp", "t", "_", "nocache",
    }

    def _normalize_url(self, url: str, base_url: str) -> str:
        """Normalize a URL: resolve relative, strip fragment, clean query params."""
        resolved = urljoin(base_url, url)
        defragged, _ = urldefrag(resolved)
        parsed = urlparse(defragged)
        path = parsed.path.rstrip("/") or "/"
        # Normalize index pages to their directory
        if path.endswith(("/index.html", "/index.htm", "/index.php")):
            path = path.rsplit("/", 1)[0] or "/"

        # Keep meaningful query params, strip tracking/session junk
        clean_query = ""
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=False)
            kept = {k: v for k, v in params.items() if k.lower() not in self.STRIP_PARAMS}
            if kept:
                clean_query = "?" + urlencode(kept, doseq=True)

        return f"{parsed.scheme}://{parsed.netloc}{path}{clean_query}"

    def _is_same_domain(self, url: str, base_domain: str) -> bool:
        """Check if URL belongs to the same domain (including subdomains)."""
        parsed = urlparse(url)
        candidate = parsed.netloc.lower()
        base = base_domain.lower()
        return candidate == base or candidate.endswith("." + base)

    def _should_exclude(self, url: str, exclude_patterns: List[str]) -> bool:
        """Check if URL matches any exclude pattern."""
        url_lower = url.lower()
        for pattern in exclude_patterns:
            if pattern.lower() in url_lower:
                return True
        return False

    def _is_skippable_url(self, url: str) -> bool:
        """Check if URL points to a non-HTML file (PDF, image, zip, etc.)."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in self.SKIP_EXTENSIONS)

    # ──────────────────────────────────────────────────────────────
    # BFS Crawler
    # ──────────────────────────────────────────────────────────────

    def _fetch_sitemap_urls(self, start_url: str, base_domain: str, exclude_patterns: List[str]) -> List[str]:
        """
        Try to fetch and parse sitemap.xml to discover all pages upfront.
        This bypasses depth limits — if a sitemap exists, we get every page.
        Returns list of URLs found, or empty list if no sitemap.
        """
        parsed = urlparse(start_url)
        sitemap_candidates = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap/sitemap.xml",
        ]

        all_urls = []

        for sitemap_url in sitemap_candidates:
            try:
                resp = self.session.get(sitemap_url, timeout=10)
                if resp.status_code != 200:
                    continue

                content_type = resp.headers.get("Content-Type", "").lower()
                if "xml" not in content_type and "text" not in content_type:
                    continue

                urls = self._parse_sitemap_xml(resp.text, base_domain, exclude_patterns)
                if urls:
                    print(f"[WebScraper] Found sitemap at {sitemap_url}: {len(urls)} URLs")
                    all_urls.extend(urls)
                    break  # Use first valid sitemap found

            except Exception as e:
                print(f"[WebScraper] Sitemap fetch failed ({sitemap_url}): {e}")
                continue

        return all_urls

    def _parse_sitemap_xml(self, xml_text: str, base_domain: str, exclude_patterns: List[str]) -> List[str]:
        """Parse sitemap XML and extract URLs. Handles sitemap index files too."""
        urls = []
        try:
            root = ET.fromstring(xml_text)
            # Strip namespace for easier parsing
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"

            # Check if this is a sitemap index (contains other sitemaps)
            sitemap_tags = root.findall(f".//{ns}sitemap")
            if sitemap_tags:
                print(f"[WebScraper] Sitemap index found with {len(sitemap_tags)} sub-sitemaps")
                for sm in sitemap_tags[:5]:  # Limit to 5 sub-sitemaps
                    loc = sm.find(f"{ns}loc")
                    if loc is not None and loc.text:
                        try:
                            sub_resp = self.session.get(loc.text.strip(), timeout=10)
                            if sub_resp.status_code == 200:
                                sub_urls = self._parse_sitemap_xml(sub_resp.text, base_domain, exclude_patterns)
                                urls.extend(sub_urls)
                        except Exception:
                            continue
                return urls

            # Regular sitemap — extract <url><loc> entries
            for url_tag in root.findall(f".//{ns}url"):
                loc = url_tag.find(f"{ns}loc")
                if loc is not None and loc.text:
                    url = loc.text.strip()
                    if self._is_same_domain(url, base_domain) and not self._should_exclude(url, exclude_patterns):
                        urls.append(url)

        except ET.ParseError as e:
            print(f"[WebScraper] Sitemap XML parse error: {e}")

        return urls

    def _crawl_website(self, start_url: str, max_pages: int, max_depth: int) -> List[Dict[str, Any]]:
        """
        Crawl a website using sitemap + BFS hybrid strategy.

        Strategy:
        1. Try sitemap.xml first — gives us ALL pages regardless of depth
        2. If no sitemap (or sitemap is partial), fall back to BFS link discovery
        3. max_pages is the hard cap either way

        Returns list of {"url", "html", "status_code", "depth", "content_type"} dicts.
        """
        crawl_delay = float(self.config.settings.get("crawl_delay", 1.0))
        exclude_patterns = self.config.settings.get("exclude_patterns", [])
        priority_paths = self.config.settings.get("priority_paths", [])

        base_parsed = urlparse(start_url)
        base_domain = base_parsed.netloc

        # BFS state
        visited: Set[str] = set()
        queue: deque = deque()
        results: List[Dict[str, Any]] = []

        # ── Step 1: Try sitemap for comprehensive page discovery ──
        sitemap_urls = self._fetch_sitemap_urls(start_url, base_domain, exclude_patterns)
        sitemap_found = len(sitemap_urls) > 0

        if sitemap_found:
            print(f"[WebScraper] Sitemap discovered {len(sitemap_urls)} pages — using sitemap-first strategy")
            # Add sitemap URLs at depth 1 (they're all "one click" from sitemap)
            for surl in sitemap_urls:
                normalized = self._normalize_url(surl, start_url)
                if normalized not in visited:
                    visited.add(normalized)
                    queue.append((normalized, 1))
        else:
            print(f"[WebScraper] No sitemap found — using BFS with depth={max_depth}")

        # ── Step 2: Seed the queue with start URL + priority paths ──
        normalized_start = self._normalize_url(start_url, start_url)
        if normalized_start not in visited:
            # If sitemap was found, start URL goes to end; otherwise it's first
            visited.add(normalized_start)
            queue.appendleft((normalized_start, 0))  # Always process start URL first

        for ppath in priority_paths:
            ppath = ppath.strip()
            if ppath:
                priority_url = self._normalize_url(ppath, start_url)
                if priority_url not in visited and self._is_same_domain(priority_url, base_domain):
                    queue.appendleft((priority_url, 1))
                    visited.add(priority_url)

        print(f"[WebScraper] Crawl starting: {start_url} (max_pages={max_pages}, max_depth={max_depth}, queue={len(queue)} URLs)")

        # ── Step 3: Fetch pages (BFS with link discovery as backup) ──
        skipped = 0
        while queue and len(results) < max_pages:
            url, depth = queue.popleft()

            # Skip non-HTML file extensions BEFORE making any request
            if self._is_skippable_url(url):
                skipped += 1
                continue

            # Domain circuit breaker: skip URLs from domains with too many consecutive failures
            url_domain = urlparse(url).netloc
            domain_fails = self._domain_failures.get(url_domain, 0)
            if domain_fails >= self.DOMAIN_FAILURE_THRESHOLD:
                self._domain_skipped[url_domain] = self._domain_skipped.get(url_domain, 0) + 1
                if self._domain_skipped[url_domain] == 1:
                    print(f"[WebScraper] Circuit breaker: skipping domain {url_domain} after {domain_fails} consecutive failures", flush=True)
                continue

            try:
                print(f"[WebScraper] Fetching [{len(results)+1}/{max_pages}] depth={depth}: {url[:80]}", flush=True)

                resp = self.session.get(
                    url,
                    timeout=self.timeout,
                    allow_redirects=True,
                )

                # Reset domain failure counter on success
                if url_domain in self._domain_failures:
                    self._domain_failures[url_domain] = 0

                # Check content type — only process HTML
                content_type = resp.headers.get("Content-Type", "").lower()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    print(f"[WebScraper] Skipping non-HTML: {content_type} ({url[:60]})", flush=True)
                    continue

                # Check content length
                content_length = resp.headers.get("Content-Length")
                if content_length and int(content_length) > self.MAX_PAGE_SIZE:
                    print(f"[WebScraper] Skipping oversized page: {content_length} bytes")
                    continue

                html = resp.text

                if not html or len(html.strip()) < 100:
                    print(f"[WebScraper] Skipping empty page")
                    continue

                # Add redirected URL to visited set to avoid re-crawling
                final_url = self._normalize_url(resp.url, resp.url)
                visited.add(final_url)

                results.append({
                    "url": resp.url,
                    "html": html,
                    "status_code": resp.status_code,
                    "depth": depth,
                    "content_type": content_type,
                })

                self.success_count += 1

                # Discover links via BFS — even if we used sitemap, this catches
                # pages the sitemap might have missed
                if depth < max_depth:
                    new_links = self._extract_links(html, resp.url, base_domain, exclude_patterns)
                    for link in new_links:
                        if link not in visited and len(visited) < max_pages * 3:
                            visited.add(link)
                            queue.append((link, depth + 1))

                # Rate limiting
                if crawl_delay > 0:
                    time.sleep(crawl_delay)

            except requests.exceptions.Timeout:
                self._domain_failures[url_domain] = self._domain_failures.get(url_domain, 0) + 1
                fail_count = self._domain_failures[url_domain]
                print(f"[WebScraper] Timeout fetching ({fail_count}/{self.DOMAIN_FAILURE_THRESHOLD} for {url_domain}): {url[:80]}", flush=True)
                self.error_count += 1
            except requests.exceptions.ConnectionError as e:
                self._domain_failures[url_domain] = self._domain_failures.get(url_domain, 0) + 1
                fail_count = self._domain_failures[url_domain]
                print(f"[WebScraper] Connection error ({fail_count}/{self.DOMAIN_FAILURE_THRESHOLD} for {url_domain}): {url[:80]} - {e}", flush=True)
                self.error_count += 1
            except Exception as e:
                self._domain_failures[url_domain] = self._domain_failures.get(url_domain, 0) + 1
                print(f"[WebScraper] Error fetching {url[:80]}: {e}", flush=True)
                traceback.print_exc()
                self.error_count += 1

        # Log circuit breaker summary
        total_circuit_skipped = sum(self._domain_skipped.values())
        circuit_breaker_info = ""
        if self._domain_skipped:
            circuit_breaker_info = f", {total_circuit_skipped} skipped by circuit breaker ({', '.join(f'{d}: {c}' for d, c in self._domain_skipped.items())})"

        print(f"[WebScraper] Crawl complete: {len(results)} pages fetched, {skipped} skipped (non-HTML), "
              f"{self.error_count} errors{circuit_breaker_info} (sitemap={'yes' if sitemap_found else 'no'})", flush=True)
        return results

    def _extract_links(self, html: str, page_url: str, base_domain: str, exclude_patterns: List[str]) -> List[str]:
        """Extract and filter links from an HTML page."""
        links = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"].strip()
                if not href or href.startswith(("javascript:", "mailto:", "tel:", "data:", "file:")):
                    continue

                normalized = self._normalize_url(href, page_url)

                if not self._is_same_domain(normalized, base_domain):
                    continue

                if self._should_exclude(normalized, exclude_patterns):
                    continue

                # Skip non-HTML file links at discovery time
                if self._is_skippable_url(normalized):
                    continue

                links.append(normalized)
        except Exception as e:
            print(f"[WebScraper] Error extracting links: {e}")

        return links

    # ──────────────────────────────────────────────────────────────
    # Content Extraction
    # ──────────────────────────────────────────────────────────────

    def _extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        Smart content extraction from HTML.
        Returns {title, content, meta_description, word_count, images_found}.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title = self._extract_title(soup)

        # Extract meta info
        meta = self._extract_meta(soup)

        # Extract image descriptions BEFORE removing tags
        image_descriptions = self._extract_images(soup, url)

        # Extract icon text BEFORE removing elements
        icon_descriptions = self._extract_icons(soup)

        # Extract SVG descriptions
        svg_descriptions = self._extract_svgs(soup)

        # Extract table data
        table_text = self._extract_tables(soup)

        # Extract JSON-LD structured data
        structured_data = self._extract_structured_data(soup)

        # Remove noise elements
        for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # Remove nav/footer/header but keep their text if it's substantial
        for tag_name in ["nav", "footer", "header", "aside"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Find main content area
        main_content = self._find_main_content(soup)

        # Convert to text
        if self.h2t and main_content:
            main_text = self.h2t.handle(str(main_content)).strip()
        elif main_content:
            main_text = main_content.get_text(separator="\n", strip=True)
        else:
            main_text = ""

        # Clean up excessive whitespace
        main_text = re.sub(r"\n{3,}", "\n\n", main_text)

        # Assemble final content
        sections = []

        if main_text:
            sections.append(main_text)

        if image_descriptions:
            sections.append("\n--- Images ---\n" + "\n".join(image_descriptions))

        if icon_descriptions:
            sections.append("\n--- UI Elements ---\n" + "\n".join(icon_descriptions))

        if svg_descriptions:
            sections.append("\n--- Graphics ---\n" + "\n".join(svg_descriptions))

        if table_text:
            sections.append("\n--- Tables ---\n" + table_text)

        if structured_data:
            sections.append("\n--- Structured Data ---\n" + structured_data)

        content = "\n\n".join(sections)

        # Add meta description at the top if available and not already in content
        if meta.get("description") and meta["description"] not in content[:500]:
            content = f"Page description: {meta['description']}\n\n{content}"

        return {
            "title": title,
            "content": content,
            "meta_description": meta.get("description", ""),
            "meta_keywords": meta.get("keywords", ""),
            "word_count": len(content.split()),
            "images_found": len(image_descriptions),
        }

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract page title with fallback chain."""
        # <title> tag
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            return title_tag.string.strip()

        # og:title
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"].strip()

        # First <h1>
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return "Untitled Page"

    def _extract_meta(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract meta description, keywords, and OG tags."""
        meta = {}

        desc = soup.find("meta", attrs={"name": "description"})
        if desc and desc.get("content"):
            meta["description"] = desc["content"].strip()

        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content") and "description" not in meta:
            meta["description"] = og_desc["content"].strip()

        keywords = soup.find("meta", attrs={"name": "keywords"})
        if keywords and keywords.get("content"):
            meta["keywords"] = keywords["content"].strip()

        return meta

    def _extract_images(self, soup: BeautifulSoup, page_url: str) -> List[str]:
        """
        Extract image descriptions. Uses alt text if available,
        falls back to OCR for images without alt text.
        """
        descriptions = []
        ocr_count = 0

        for img in soup.find_all("img"):
            # Try alt text first
            alt = img.get("alt", "").strip()
            title = img.get("title", "").strip()
            aria_label = img.get("aria-label", "").strip()

            if alt and alt.lower() not in ("", "image", "photo", "img", "icon", "logo"):
                descriptions.append(f"[Image: {alt}]")
                continue

            if title:
                descriptions.append(f"[Image: {title}]")
                continue

            if aria_label:
                descriptions.append(f"[Image: {aria_label}]")
                continue

            # No text description — try OCR if available
            if OCR_AVAILABLE and ocr_count < self.MAX_OCR_PER_PAGE:
                src = img.get("src", "")
                if src:
                    ocr_text = self._ocr_image(src, page_url)
                    if ocr_text:
                        descriptions.append(f"[Image text: {ocr_text}]")
                        ocr_count += 1
                        continue

            # Fallback: use filename
            src = img.get("src", "")
            if src:
                filename = src.split("/")[-1].split("?")[0]
                if filename and len(filename) < 100:
                    # Clean up common image naming patterns
                    name = re.sub(r"[-_]", " ", filename.rsplit(".", 1)[0])
                    if name and len(name) > 2:
                        descriptions.append(f"[Image: {name}]")

        return descriptions

    def _ocr_image(self, src: str, page_url: str) -> Optional[str]:
        """Download an image and run OCR on it. Returns extracted text or None."""
        try:
            # Resolve relative URL
            img_url = urljoin(page_url, src)

            # Skip data URIs, SVGs
            if img_url.startswith("data:") or img_url.endswith(".svg"):
                return None

            # Download image with size limit
            resp = self.session.get(img_url, timeout=self.OCR_TIMEOUT, stream=True)
            if resp.status_code != 200:
                return None

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > self.MAX_IMAGE_DOWNLOAD:
                return None

            img_data = resp.content
            if len(img_data) > self.MAX_IMAGE_DOWNLOAD:
                return None

            # Open with Pillow
            img = Image.open(io.BytesIO(img_data))

            # Skip tiny images (icons, spacers)
            width, height = img.size
            if width < self.MIN_IMAGE_SIZE or height < self.MIN_IMAGE_SIZE:
                return None

            # Convert to RGB if needed
            if img.mode not in ("L", "RGB"):
                img = img.convert("RGB")

            # Run OCR
            text = pytesseract.image_to_string(img, timeout=self.OCR_TIMEOUT).strip()

            # Only return if we got meaningful text
            if text and len(text) > 3 and not text.isspace():
                # Clean up OCR artifacts
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 500:
                    text = text[:500] + "..."
                return text

        except Exception as e:
            # Silently skip failed OCR — not critical
            pass

        return None

    def _extract_icons(self, soup: BeautifulSoup) -> List[str]:
        """Detect icon fonts and map to text labels."""
        descriptions = []
        seen = set()

        # Font Awesome: <i class="fa fa-home"></i> or <i class="fas fa-home"></i>
        for el in soup.find_all(class_=re.compile(r"\bfa[srlb]?\b")):
            classes = el.get("class", [])
            for cls in classes:
                if cls.startswith("fa-") and cls in ICON_MAP:
                    label = ICON_MAP[cls]
                    # Check aria-label for more context
                    aria = el.get("aria-label", "").strip()
                    desc = aria if aria else label
                    if desc not in seen:
                        descriptions.append(f"[Icon: {desc}]")
                        seen.add(desc)
                    break

        # Material Icons: <span class="material-icons">home</span>
        for el in soup.find_all(class_=re.compile(r"material-icons|material-symbols")):
            icon_name = el.get_text(strip=True).lower()
            if icon_name in ICON_MAP:
                label = ICON_MAP[icon_name]
                if label not in seen:
                    descriptions.append(f"[Icon: {label}]")
                    seen.add(label)
            elif icon_name and icon_name not in seen:
                # Unknown material icon — use the name directly
                clean_name = icon_name.replace("_", " ").title()
                descriptions.append(f"[Icon: {clean_name}]")
                seen.add(icon_name)

        # Glyphicons: <span class="glyphicon glyphicon-home"></span>
        for el in soup.find_all(class_=re.compile(r"glyphicon-")):
            classes = el.get("class", [])
            for cls in classes:
                if cls.startswith("glyphicon-") and cls != "glyphicon":
                    name = cls.replace("glyphicon-", "").replace("-", " ").title()
                    if name not in seen:
                        descriptions.append(f"[Icon: {name}]")
                        seen.add(name)
                    break

        # Any element with aria-label that looks like an icon (no visible text)
        for el in soup.find_all(attrs={"aria-label": True}):
            if not el.get_text(strip=True) and el.get("aria-label"):
                label = el["aria-label"].strip()
                if label and label not in seen and len(label) < 50:
                    descriptions.append(f"[Icon: {label}]")
                    seen.add(label)

        return descriptions

    def _extract_svgs(self, soup: BeautifulSoup) -> List[str]:
        """Extract descriptions from SVG elements."""
        descriptions = []

        for svg in soup.find_all("svg"):
            # Check <title> child
            title = svg.find("title")
            if title and title.get_text(strip=True):
                descriptions.append(f"[SVG: {title.get_text(strip=True)}]")
                continue

            # Check <desc> child
            desc = svg.find("desc")
            if desc and desc.get_text(strip=True):
                descriptions.append(f"[SVG: {desc.get_text(strip=True)}]")
                continue

            # Check aria-label
            aria = svg.get("aria-label", "").strip()
            if aria:
                descriptions.append(f"[SVG: {aria}]")

        return descriptions

    def _extract_tables(self, soup: BeautifulSoup) -> str:
        """Convert HTML tables to readable text."""
        tables_text = []

        for table in soup.find_all("table"):
            rows = []

            # Header
            thead = table.find("thead")
            if thead:
                header_cells = [th.get_text(strip=True) for th in thead.find_all(["th", "td"])]
                if header_cells:
                    rows.append(" | ".join(header_cells))
                    rows.append("-" * len(rows[0]))

            # Body
            tbody = table.find("tbody")
            if tbody:
                body_rows = tbody.find_all("tr")
            else:
                # No <tbody> — use all <tr> but skip ones inside <thead>
                body_rows = [tr for tr in table.find_all("tr") if not tr.find_parent("thead")]
            for tr in body_rows:
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(" | ".join(cells))

            if rows:
                tables_text.append("\n".join(rows))

            # Limit table extraction
            if len(tables_text) >= 10:
                break

        return "\n\n".join(tables_text)

    def _extract_structured_data(self, soup: BeautifulSoup) -> str:
        """Extract JSON-LD structured data."""
        parts = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    name = data.get("name", data.get("headline", ""))
                    desc = data.get("description", "")
                    stype = data.get("@type", "")
                    if name or desc:
                        parts.append(f"{stype}: {name} - {desc}".strip(" -"))
            except (json.JSONDecodeError, TypeError):
                continue

        return "\n".join(parts) if parts else ""

    def _find_main_content(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main content area of the page."""
        # Try semantic elements first
        for selector in ["main", "article", '[role="main"]']:
            el = soup.find(selector) if not selector.startswith("[") else soup.find(attrs={"role": "main"})
            if el:
                return el

        # Try common class/id patterns
        for attr in ["id", "class"]:
            for pattern in ["content", "main", "body", "post", "entry", "article"]:
                if attr == "id":
                    el = soup.find(id=re.compile(pattern, re.I))
                else:
                    el = soup.find(class_=re.compile(pattern, re.I))
                if el and len(el.get_text(strip=True)) > 100:
                    return el

        # Fallback to body
        return soup.find("body") or soup

    # ──────────────────────────────────────────────────────────────
    # Connector interface
    # ──────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        return self._connect_sync()

    # Connection test uses a longer timeout and retries
    CONNECT_TIMEOUT = 30  # seconds (longer than per-page timeout)
    CONNECT_RETRIES = 2

    def _connect_sync(self) -> bool:
        """Test connection by fetching the start URL. Retries on timeout."""
        print("[WebScraper] _connect_sync() called", flush=True)

        start_url = self.config.settings.get("start_url", "").strip()
        if not start_url:
            self._set_error("No start_url configured")
            print("[WebScraper] ERROR: No start_url configured", flush=True)
            return False

        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url
            self.config.settings["start_url"] = start_url

        print(f"[WebScraper] Testing connection to: {start_url}", flush=True)

        last_error = None
        for attempt in range(1, self.CONNECT_RETRIES + 1):
            try:
                resp = self.session.get(start_url, timeout=self.CONNECT_TIMEOUT, allow_redirects=True)
                print(f"[WebScraper] Connection test (attempt {attempt}): status={resp.status_code}, "
                      f"content-type={resp.headers.get('Content-Type', 'unknown')}, "
                      f"size={len(resp.content)} bytes", flush=True)

                if resp.status_code < 400:
                    self.status = ConnectorStatus.CONNECTED
                    return True
                else:
                    last_error = f"HTTP {resp.status_code} from {start_url}"
                    print(f"[WebScraper] ERROR: {last_error}", flush=True)

            except requests.exceptions.Timeout:
                last_error = f"Timeout ({self.CONNECT_TIMEOUT}s) connecting to {start_url}"
                print(f"[WebScraper] ERROR (attempt {attempt}/{self.CONNECT_RETRIES}): {last_error}", flush=True)
            except requests.exceptions.ConnectionError as e:
                last_error = f"Cannot reach {start_url}: {e}"
                print(f"[WebScraper] ERROR (attempt {attempt}/{self.CONNECT_RETRIES}): {last_error}", flush=True)
            except Exception as e:
                last_error = f"Connection error: {type(e).__name__}: {e}"
                print(f"[WebScraper] ERROR (attempt {attempt}/{self.CONNECT_RETRIES}): {last_error}", flush=True)
                traceback.print_exc()

            # Wait before retry
            if attempt < self.CONNECT_RETRIES:
                wait = 3 * attempt
                print(f"[WebScraper] Retrying in {wait}s...", flush=True)
                time.sleep(wait)

        self._set_error(last_error or "Connection failed after retries")
        print(f"[WebScraper] FINAL: Connection failed after {self.CONNECT_RETRIES} attempts: {last_error}", flush=True)
        return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        return self._sync_sync(since)

    def _sync_sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Main sync — crawl website and return Documents."""
        print(f"[WebScraper] ========== SYNC START ==========")

        if self.status != ConnectorStatus.CONNECTED:
            if not self._connect_sync():
                error_msg = self.last_error or "Connection failed"
                print(f"[WebScraper] Connection failed: {error_msg}", flush=True)
                raise ConnectionError(f"Cannot reach website: {error_msg}")

        self.status = ConnectorStatus.SYNCING
        documents = []

        start_url = self.config.settings.get("start_url", "")
        max_pages = int(self.config.settings.get("max_pages", 50))
        max_depth = int(self.config.settings.get("max_depth", 5))

        print(f"[WebScraper] Crawling: {start_url}")
        print(f"[WebScraper] Max pages: {max_pages}, Max depth: {max_depth}")
        print(f"[WebScraper] OCR enabled: {OCR_AVAILABLE}")

        try:
            # BFS crawl
            pages = self._crawl_website(start_url, max_pages, max_depth)
            print(f"[WebScraper] Processing {len(pages)} pages for content extraction")

            for i, page in enumerate(pages):
                try:
                    extracted = self._extract_content(page["html"], page["url"])

                    content = extracted["content"]
                    title = extracted["title"]

                    print(f"[WebScraper] Page {i+1}: {page['url'][:60]}... ({extracted['word_count']} words, {extracted['images_found']} images)")

                    # Skip pages with too little content
                    if len(content.strip()) < 50:
                        print(f"[WebScraper] Skipping - too short ({len(content.strip())} chars)")
                        continue

                    doc = Document(
                        doc_id=f"webscraper_{self._url_to_filename(page['url'])}",
                        source="webscraper",
                        content=content,
                        title=title,
                        metadata={
                            "url": page["url"],
                            "word_count": extracted["word_count"],
                            "meta_description": extracted.get("meta_description", ""),
                            "depth": page["depth"],
                            "images_found": extracted["images_found"],
                        },
                        timestamp=datetime.now(),
                        url=page["url"],
                        doc_type="webpage",
                    )
                    documents.append(doc)
                    self.success_count += 1

                except Exception as e:
                    print(f"[WebScraper] Error processing page {i}: {e}")
                    traceback.print_exc()
                    self.error_count += 1

        except Exception as e:
            print(f"[WebScraper] CRAWL FAILED: {e}")
            traceback.print_exc()
            self._set_error(str(e))
            raise

        print(f"[WebScraper] ========== SYNC DONE ==========")
        print(f"[WebScraper] Documents: {len(documents)}, Success: {self.success_count}, Errors: {self.error_count}")

        self.status = ConnectorStatus.CONNECTED
        return documents

    async def disconnect(self) -> bool:
        self.session.close()
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def get_document(self, doc_id: str) -> Optional[Document]:
        return None

    async def test_connection(self) -> bool:
        return self._connect_sync()
