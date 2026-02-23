#!/usr/bin/env python3
"""
UCLA CTSI Research Cores Scraper

Scrapes all ~80 UCLA CTSI research core facilities in 3 levels:
  Level 1: Paginate listing pages, collect facility URLs
  Level 2: Scrape each facility detail page for structured data + external links
  Level 3: Full-crawl external websites via Firecrawl connector

Usage:
  python -m scripts.scrape_ctsi scrape
  python -m scripts.scrape_ctsi scrape --skip-firecrawl
  python -m scripts.scrape_ctsi scrape --max-firecrawl-pages 20
  python -m scripts.scrape_ctsi ingest
  python -m scripts.scrape_ctsi ingest --tenant-id <id> --user-id <id>
  python -m scripts.scrape_ctsi scrape+ingest
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CTSI_BASE_URL = "https://ctsi.ucla.edu"
LISTING_URL = (
    "https://ctsi.ucla.edu/pages/search"
    "?f[0]=page_category:1436"
    "&f[1]=page_tag:1381"
    "&f[2]=page_tag:1386"
    "&f[3]=page_tag:1771"
    "&f[4]=page_tag:1776"
    "&keywords="
)

# Output directory (relative to backend/)
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BACKEND_DIR, "scraped_data", "ctsi")
PROGRESS_FILE = os.path.join(OUTPUT_DIR, "_progress.json")
COMBINED_FILE = os.path.join(OUTPUT_DIR, "_all_facilities.json")

# Scraping settings
MAX_LISTING_PAGES = 8  # pages 0-7
REQUEST_DELAY = 1.5  # seconds between requests (be polite)
DEFAULT_MAX_FIRECRAWL_PAGES = 50


# ---------------------------------------------------------------------------
# Session & Progress Helpers
# ---------------------------------------------------------------------------

def get_session() -> requests.Session:
    """Create a requests.Session with browser-like headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    })
    return session


def load_progress() -> Dict[str, Any]:
    """Load scraping progress from JSON file for resume support."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "listing_complete": False,
        "facilities": [],
        "facilities_scraped": [],
        "external_sites_crawled": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_progress(progress: Dict[str, Any]) -> None:
    """Save scraping progress to JSON file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    progress["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


# ---------------------------------------------------------------------------
# Level 1: Listing Page Scraper
# ---------------------------------------------------------------------------

def scrape_listing_pages(session: requests.Session) -> List[Dict[str, str]]:
    """
    Paginate through all CTSI listing pages and extract facility links.

    Returns a list of dicts: [{"url": "/slug", "name": "Facility Name"}, ...]
    """
    facilities: List[Dict[str, str]] = []
    seen_urls: set = set()

    for page_num in range(MAX_LISTING_PAGES):
        page_url = f"{LISTING_URL}&page={page_num}"
        print(f"[Level 1] Fetching listing page {page_num + 1}/{MAX_LISTING_PAGES}: {page_url}")

        try:
            resp = session.get(page_url, timeout=60)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[Level 1] ERROR fetching page {page_num}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Facility links appear as <h3><a href="/slug">Name</a></h3>
        # inside the search results area. We look for all h3 > a with
        # relative paths that are NOT navigation/utility links.
        count_before = len(facilities)

        for h3 in soup.find_all("h3"):
            link = h3.find("a", href=True)
            if not link:
                continue
            href = link["href"].strip()
            name = link.get_text(strip=True)

            # Skip non-facility links (navigation, external, anchors)
            if not href.startswith("/"):
                continue
            # Skip common non-facility paths
            if href in ("/", "/pages/search") or href.startswith("/pages/"):
                continue
            # Skip if it looks like a utility/admin page
            if any(skip in href for skip in ["/user/", "/admin/", "/search", "/node/"]):
                continue
            # Deduplicate
            if href in seen_urls:
                continue

            seen_urls.add(href)
            facilities.append({
                "url": href,
                "name": name,
                "full_url": urljoin(CTSI_BASE_URL, href),
            })

        found_on_page = len(facilities) - count_before
        print(f"[Level 1] Found {found_on_page} facilities on page {page_num + 1}")

        # Be polite
        if page_num < MAX_LISTING_PAGES - 1:
            time.sleep(REQUEST_DELAY)

    print(f"[Level 1] Total facilities found: {len(facilities)}")
    return facilities


# ---------------------------------------------------------------------------
# Level 2: Facility Detail Page Scraper
# ---------------------------------------------------------------------------

def _extract_external_urls(soup: BeautifulSoup, page_url: str) -> List[Dict[str, str]]:
    """
    Extract external URLs from a facility detail page.

    Looks for links that go outside CTSI domain, preferring links with
    keywords like 'website', 'visit', 'more information'.
    """
    external_links: List[Dict[str, str]] = []
    seen: set = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True).lower()

        # Skip anchors, javascript, mailto
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        # Skip relative paths (internal CTSI links)
        if href.startswith("/"):
            continue

        parsed = urlparse(href)
        domain = parsed.netloc.lower()

        # Skip CTSI internal links
        if "ctsi.ucla.edu" in domain:
            continue
        # Skip common non-facility links (social media, generic UCLA, footer nav)
        skip_domains = [
            "facebook.com", "twitter.com", "instagram.com",
            "linkedin.com", "youtube.com", "x.com",
            "accessibility.ucla.edu", "privacy.ucla.edu",
            "registrar.ucla.edu", "emergency.ucla.edu",
            "bso.ucla.edu",           # UCLA emergency/safety
            "www.ucla.edu",           # Generic UCLA links
            "eepurl.com",             # Newsletter signup
            "profiles.ucla.edu",      # Collaborator profiles
            "biodesign.ucla.edu",     # Biodesign (site-wide link)
            "researchgo.ucla.edu",    # ResearchGo (site-wide nav)
            "cedars-sinai.edu",       # Cedars-Sinai (site-wide footer)
            "cdrewu.edu",            # CDU (site-wide footer)
            "lundquist.org",         # Lundquist (site-wide footer)
            "uclahealth.org",        # UCLA Health privacy
        ]
        if any(sd in domain for sd in skip_domains):
            continue

        # Deduplicate
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)

        # Determine priority based on link text
        priority = 0
        priority_keywords = ["website", "visit", "more information", "web site",
                             "home page", "homepage", "learn more", "official"]
        for kw in priority_keywords:
            if kw in text:
                priority = 1
                break

        external_links.append({
            "url": href,
            "text": a.get_text(strip=True),
            "priority": priority,
        })

    # Sort so higher-priority links come first
    external_links.sort(key=lambda x: -x["priority"])
    return external_links


def _extract_services(soup: BeautifulSoup, text_content: str) -> List[str]:
    """
    Extract a services list from the facility page.

    Looks for <ul>/<ol> lists and numbered items in text.
    """
    services: List[str] = []

    # Strategy 1: Look for HTML lists (ul/ol) in the main content area
    main_content = soup.find("main") or soup.find("article") or soup.find("div", class_=re.compile(r"content|main|body", re.I))
    search_area = main_content if main_content else soup

    for list_el in search_area.find_all(["ul", "ol"]):
        for li in list_el.find_all("li"):
            item_text = li.get_text(strip=True)
            if item_text and len(item_text) > 3 and len(item_text) < 500:
                services.append(item_text)

    # Strategy 2: If no list found, look for numbered items in text
    if not services:
        # Pattern: "1. item", "2) item", "(1) item"
        numbered_pattern = re.compile(
            r'(?:^|\n)\s*(?:\d+[.)]\s*|\(\d+\)\s*)(.+?)(?=\n\s*(?:\d+[.)]\s*|\(\d+\)\s*)|$)',
            re.MULTILINE
        )
        matches = numbered_pattern.findall(text_content)
        for match in matches:
            item = match.strip()
            if item and len(item) > 3 and len(item) < 500:
                services.append(item)

    return services


def scrape_facility_page(session: requests.Session, facility: Dict[str, str]) -> Dict[str, Any]:
    """
    Scrape a single CTSI facility detail page.

    Returns structured data: name, description, services, external URLs,
    full page content as text.
    """
    url = facility["full_url"]
    print(f"[Level 2] Scraping: {facility['name']} ({url})")

    result: Dict[str, Any] = {
        "slug": facility["url"],
        "ctsi_url": url,
        "name": facility["name"],
        "description": "",
        "services": [],
        "external_urls": [],
        "primary_external_url": None,
        "full_text": "",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "error": None,
    }

    try:
        resp = session.get(url, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        result["error"] = str(e)
        print(f"[Level 2] ERROR fetching {url}: {e}")
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract title from <h1>
    h1 = soup.find("h1")
    if h1:
        result["name"] = h1.get_text(strip=True)

    # Get main content area (try multiple selectors)
    main_content = (
        soup.find("main")
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"content|field--name-body", re.I))
        or soup.find("div", id=re.compile(r"content|main", re.I))
    )

    # Extract full text content (strip navigation, footer, etc.)
    if main_content:
        # Remove nav, header, footer elements from the content area
        for tag in main_content.find_all(["nav", "header", "footer", "script", "style"]):
            tag.decompose()
        full_text = main_content.get_text(separator="\n", strip=True)
    else:
        # Fallback: get body text, stripping obvious non-content
        body = soup.find("body")
        if body:
            for tag in body.find_all(["nav", "header", "footer", "script", "style", "aside"]):
                tag.decompose()
            full_text = body.get_text(separator="\n", strip=True)
        else:
            full_text = soup.get_text(separator="\n", strip=True)

    result["full_text"] = full_text

    # Extract description: first substantial paragraph after h1
    # Look for paragraphs in the content area
    content_area = main_content if main_content else soup
    paragraphs = content_area.find_all("p")
    description_parts = []
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 30:  # Skip very short paragraphs (likely headers/labels)
            description_parts.append(text)
    result["description"] = "\n\n".join(description_parts)

    # Extract services
    result["services"] = _extract_services(soup, full_text)

    # Extract external URLs
    result["external_urls"] = _extract_external_urls(soup, url)

    # Pick primary external URL (highest priority, first match)
    if result["external_urls"]:
        result["primary_external_url"] = result["external_urls"][0]["url"]

    print(f"[Level 2]   -> Description: {len(result['description'])} chars, "
          f"Services: {len(result['services'])}, "
          f"External URLs: {len(result['external_urls'])}, "
          f"Primary: {result['primary_external_url']}")

    return result


def scrape_all_facilities(
    session: requests.Session,
    facilities: List[Dict[str, str]],
    progress: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Scrape all facility detail pages with resume support.

    Saves each facility as an individual JSON file and updates progress.
    """
    scraped = progress.get("facilities_scraped", [])
    scraped_set = set(scraped)
    results: List[Dict[str, Any]] = []

    # Load already-scraped results from disk
    for slug in scraped:
        filepath = os.path.join(OUTPUT_DIR, f"{_slug_to_filename(slug)}.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    results.append(json.load(f))
            except (json.JSONDecodeError, IOError):
                pass

    total = len(facilities)
    pending = [f for f in facilities if f["url"] not in scraped_set]
    print(f"[Level 2] Scraping {len(pending)} facilities ({len(scraped)} already done, {total} total)")

    for i, facility in enumerate(pending):
        data = scrape_facility_page(session, facility)
        results.append(data)

        # Save individual JSON
        filename = _slug_to_filename(facility["url"])
        filepath = os.path.join(OUTPUT_DIR, f"{filename}.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        # Update progress
        progress.setdefault("facilities_scraped", []).append(facility["url"])
        save_progress(progress)

        print(f"[Level 2] Progress: {len(scraped) + i + 1}/{total}")

        # Be polite
        time.sleep(REQUEST_DELAY)

    return results


def _slug_to_filename(slug: str) -> str:
    """Convert a URL slug like '/some-facility' to a safe filename."""
    clean = slug.strip("/").replace("/", "_")
    # Remove any non-alphanumeric chars except hyphens and underscores
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", clean)
    return clean or "unknown"


# ---------------------------------------------------------------------------
# Level 3: Firecrawl External Site Crawling
# ---------------------------------------------------------------------------

def crawl_external_site(url: str, max_pages: int = DEFAULT_MAX_FIRECRAWL_PAGES) -> List[Dict[str, Any]]:
    """
    Use FirecrawlConnector to crawl an external website.

    Args:
        url: The external site URL to crawl.
        max_pages: Maximum pages to crawl (default 50).

    Returns:
        List of dicts with url, title, content for each crawled page.
    """
    # Import here to avoid import errors when Firecrawl is not needed
    sys.path.insert(0, BACKEND_DIR)
    from connectors.base_connector import ConnectorConfig
    from connectors.firecrawl_connector import FirecrawlConnector

    if not os.getenv("FIRECRAWL_API_KEY"):
        print(f"[Level 3] WARNING: FIRECRAWL_API_KEY not set, skipping crawl of {url}")
        return []

    print(f"[Level 3] Crawling external site: {url} (max {max_pages} pages)")

    config = ConnectorConfig(
        connector_type="firecrawl",
        user_id="ctsi_scraper",
        settings={
            "start_url": url,
            "max_pages": max_pages,
        },
    )

    connector = FirecrawlConnector(config)
    if not connector.connect():
        print(f"[Level 3] ERROR: Could not connect to Firecrawl for {url}")
        return []

    try:
        documents = connector.sync()
    except Exception as e:
        print(f"[Level 3] ERROR crawling {url}: {e}")
        traceback.print_exc()
        return []

    # Convert Document objects to dicts
    crawled_pages: List[Dict[str, Any]] = []
    for doc in documents:
        crawled_pages.append({
            "url": doc.url or "",
            "title": doc.title or "",
            "content": doc.content or "",
            "doc_type": doc.doc_type,
            "metadata": doc.metadata,
        })

    print(f"[Level 3] Crawled {len(crawled_pages)} pages from {url}")
    return crawled_pages


def crawl_all_external_sites(
    facilities: List[Dict[str, Any]],
    progress: Dict[str, Any],
    max_pages: int = DEFAULT_MAX_FIRECRAWL_PAGES,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Crawl all external websites linked from facility pages.

    Args:
        facilities: List of facility dicts (from Level 2 scraping).
        progress: Progress dict for resume support.
        max_pages: Max pages per external site.

    Returns:
        Dict mapping external URL to list of crawled page dicts.
    """
    crawled_set = set(progress.get("external_sites_crawled", []))
    all_crawled: Dict[str, List[Dict[str, Any]]] = {}

    # Collect unique external URLs with their facility context
    external_urls: List[Dict[str, str]] = []
    seen_urls: set = set()

    for facility in facilities:
        primary_url = facility.get("primary_external_url")
        if not primary_url:
            continue

        # Normalize URL
        parsed = urlparse(primary_url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")

        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)

        external_urls.append({
            "url": primary_url,
            "facility_name": facility.get("name", "Unknown"),
            "facility_slug": facility.get("slug", ""),
        })

    pending = [eu for eu in external_urls if eu["url"] not in crawled_set]
    print(f"[Level 3] Crawling {len(pending)} external sites "
          f"({len(crawled_set)} already done, {len(external_urls)} total)")

    for i, ext in enumerate(pending):
        url = ext["url"]
        print(f"[Level 3] [{i + 1}/{len(pending)}] Crawling: {url} "
              f"(facility: {ext['facility_name']})")

        pages = crawl_external_site(url, max_pages=max_pages)
        all_crawled[url] = pages

        # Save crawled data to individual file
        slug = ext["facility_slug"]
        filename = _slug_to_filename(slug)
        crawl_filepath = os.path.join(OUTPUT_DIR, "external", f"{filename}_crawl.json")
        os.makedirs(os.path.dirname(crawl_filepath), exist_ok=True)
        with open(crawl_filepath, "w") as f:
            json.dump({
                "source_url": url,
                "facility_name": ext["facility_name"],
                "facility_slug": slug,
                "pages_crawled": len(pages),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "pages": pages,
            }, f, indent=2)

        # Update progress
        progress.setdefault("external_sites_crawled", []).append(url)
        save_progress(progress)

        print(f"[Level 3] Done: {url} -> {len(pages)} pages")

    # Also load previously crawled data from disk
    external_dir = os.path.join(OUTPUT_DIR, "external")
    if os.path.isdir(external_dir):
        for fname in os.listdir(external_dir):
            if fname.endswith("_crawl.json"):
                filepath = os.path.join(external_dir, fname)
                try:
                    with open(filepath, "r") as f:
                        data = json.load(f)
                    src_url = data.get("source_url", "")
                    if src_url and src_url not in all_crawled:
                        all_crawled[src_url] = data.get("pages", [])
                except (json.JSONDecodeError, IOError):
                    pass

    return all_crawled


def fallback_scrape_external_sites(
    facilities: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Use Firecrawl single-page scraper as fallback for external sites
    that returned 0 pages from the full crawl.

    Checks the external/ directory for crawl files with 0 pages
    and scrapes those URLs individually.
    """
    sys.path.insert(0, BACKEND_DIR)
    from connectors.firecrawl_connector import FirecrawlScraper

    scraper = FirecrawlScraper()
    if not scraper.api_key:
        print("[Fallback] WARNING: FIRECRAWL_API_KEY not set, skipping fallback scrape")
        return {}

    external_dir = os.path.join(OUTPUT_DIR, "external")
    if not os.path.isdir(external_dir):
        print("[Fallback] No external/ directory found, nothing to fallback scrape")
        return {}

    # Find crawl files with 0 pages
    zero_page_files: List[Dict[str, Any]] = []
    for fname in sorted(os.listdir(external_dir)):
        if not fname.endswith("_crawl.json"):
            continue
        filepath = os.path.join(external_dir, fname)
        with open(filepath) as f:
            data = json.load(f)
        if data.get("pages_crawled", 0) == 0 and data.get("source_url"):
            zero_page_files.append({
                "filepath": filepath,
                "source_url": data["source_url"],
                "facility_name": data.get("facility_name", "Unknown"),
                "facility_slug": data.get("facility_slug", ""),
            })

    if not zero_page_files:
        print("[Fallback] All external sites already have data, nothing to do")
        return {}

    print(f"\n{'=' * 60}")
    print(f"FALLBACK: Single-page scraping {len(zero_page_files)} sites that returned 0 pages")
    print(f"{'=' * 60}")

    all_scraped: Dict[str, List[Dict[str, Any]]] = {}

    for i, item in enumerate(zero_page_files):
        url = item["source_url"]

        # Skip urldefense.com URLs (these are URL-protected links that won't resolve)
        if "urldefense.com" in url:
            print(f"[Fallback] [{i+1}/{len(zero_page_files)}] Skipping urldefense URL: {url}")
            continue

        print(f"[Fallback] [{i+1}/{len(zero_page_files)}] Scraping: {url} ({item['facility_name']})")

        result = scraper.scrape_url(url)
        if not result:
            print(f"[Fallback] Failed: {url}")
            continue

        markdown = result.get("markdown", "")
        metadata = result.get("metadata", {})
        title = metadata.get("title", "")

        if len(markdown.strip()) < 50:
            print(f"[Fallback] Too little content ({len(markdown)} chars): {url}")
            continue

        page_data = {
            "url": url,
            "title": title or item["facility_name"],
            "content": markdown,
            "doc_type": "webpage",
            "metadata": {
                "url": url,
                "description": metadata.get("description", ""),
                "word_count": len(markdown.split()),
                "crawl_engine": "firecrawl_scraper",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        pages = [page_data]
        all_scraped[url] = pages

        # Update the crawl file
        with open(item["filepath"], "w") as f:
            json.dump({
                "source_url": url,
                "facility_name": item["facility_name"],
                "facility_slug": item["facility_slug"],
                "pages_crawled": len(pages),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
                "crawl_method": "single_page_fallback",
                "pages": pages,
            }, f, indent=2)

        print(f"[Fallback] OK: {url} -> {title} ({len(markdown)} chars)")

        # Small delay to avoid rate limiting
        time.sleep(0.5)

    success_count = len(all_scraped)
    print(f"\n[Fallback] Done: {success_count}/{len(zero_page_files)} sites scraped successfully")
    return all_scraped


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_scrape(
    skip_firecrawl: bool = False,
    max_firecrawl_pages: int = DEFAULT_MAX_FIRECRAWL_PAGES,
) -> None:
    """
    Run the full scrape pipeline: Level 1 -> Level 2 -> Level 3.

    Saves combined output to _all_facilities.json.
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    session = get_session()
    progress = load_progress()

    # ---- Level 1: Listing pages ----
    if not progress.get("listing_complete"):
        print("\n" + "=" * 60)
        print("LEVEL 1: Scraping listing pages")
        print("=" * 60)
        facilities = scrape_listing_pages(session)
        progress["facilities"] = facilities
        progress["listing_complete"] = True
        save_progress(progress)
    else:
        facilities = progress["facilities"]
        print(f"[Level 1] Already complete. {len(facilities)} facilities loaded from progress.")

    # ---- Level 2: Facility detail pages ----
    print("\n" + "=" * 60)
    print("LEVEL 2: Scraping facility detail pages")
    print("=" * 60)
    facility_data = scrape_all_facilities(session, facilities, progress)

    # ---- Level 3: External site crawling ----
    external_data: Dict[str, List[Dict[str, Any]]] = {}
    if skip_firecrawl:
        print("\n[Level 3] Skipping Firecrawl crawling (--skip-firecrawl)")
    else:
        print("\n" + "=" * 60)
        print("LEVEL 3: Crawling external websites via Firecrawl")
        print("=" * 60)
        external_data = crawl_all_external_sites(
            facility_data, progress, max_pages=max_firecrawl_pages
        )

    # ---- Level 3b: Fallback single-page scrape for 0-page sites ----
    if not skip_firecrawl:
        fallback_data = fallback_scrape_external_sites(facility_data)
        external_data.update(fallback_data)

    # ---- Save combined output ----
    print("\n" + "=" * 60)
    print("Saving combined output")
    print("=" * 60)

    # Merge external crawl data into facility records
    for facility in facility_data:
        primary_url = facility.get("primary_external_url")
        if primary_url and primary_url in external_data:
            facility["external_crawl"] = {
                "pages_crawled": len(external_data[primary_url]),
                "source_url": primary_url,
            }
        else:
            facility["external_crawl"] = None

    combined = {
        "scrape_metadata": {
            "total_facilities": len(facility_data),
            "facilities_with_external_url": sum(
                1 for f in facility_data if f.get("primary_external_url")
            ),
            "external_sites_crawled": len(external_data),
            "total_external_pages": sum(len(v) for v in external_data.values()),
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "firecrawl_skipped": skip_firecrawl,
        },
        "facilities": facility_data,
    }

    with open(COMBINED_FILE, "w") as f:
        json.dump(combined, f, indent=2)

    print(f"\nDone! Combined output saved to: {COMBINED_FILE}")
    print(f"  Total facilities: {combined['scrape_metadata']['total_facilities']}")
    print(f"  With external URL: {combined['scrape_metadata']['facilities_with_external_url']}")
    print(f"  External sites crawled: {combined['scrape_metadata']['external_sites_crawled']}")
    print(f"  Total external pages: {combined['scrape_metadata']['total_external_pages']}")


def run_ingest(tenant_id: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """
    Ingest scraped CTSI data into the 2nd Brain knowledge base.

    Loads the combined JSON from _all_facilities.json and external crawl
    files, creates Document rows in the database, then runs extraction
    (structured summaries) and embedding on new documents.

    Args:
        tenant_id: Tenant ID to ingest under. If None, auto-detects first tenant.
        user_id: User ID for audit trail. If None, auto-detects first user.
    """
    # ---- Setup: Add backend to path, load .env, import DB dependencies ----
    sys.path.insert(0, BACKEND_DIR)

    from dotenv import load_dotenv
    load_dotenv(os.path.join(BACKEND_DIR, ".env"))

    from database.models import (
        Document as DBDocument,
        DocumentStatus,
        DocumentClassification,
        Tenant,
        User,
        SessionLocal,
    )
    from services.extraction_service import get_extraction_service
    from services.embedding_service import get_embedding_service

    BATCH_SIZE = 50

    # ---- Open DB session ----
    db = SessionLocal()

    try:
        # ---- Resolve tenant_id and user_id ----
        if not tenant_id:
            first_tenant = db.query(Tenant).filter(Tenant.is_active == True).first()
            if not first_tenant:
                print("[Ingest] ERROR: No active tenants found in the database.")
                print("         Create a tenant first (sign up via the UI) or pass --tenant-id.")
                return
            tenant_id = first_tenant.id
            print(f"[Ingest] Auto-detected tenant: {first_tenant.name} ({tenant_id})")

        if not user_id:
            first_user = db.query(User).filter(
                User.tenant_id == tenant_id,
                User.is_active == True,
            ).first()
            if not first_user:
                print(f"[Ingest] ERROR: No active users found for tenant {tenant_id}.")
                print("         Create a user first or pass --user-id.")
                return
            user_id = first_user.id
            print(f"[Ingest] Auto-detected user: {first_user.email} ({user_id})")

        # ---- Verify tenant and user exist ----
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            print(f"[Ingest] ERROR: Tenant {tenant_id} not found in database.")
            return

        user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
        if not user:
            print(f"[Ingest] ERROR: User {user_id} not found in tenant {tenant_id}.")
            return

        print(f"\n{'=' * 60}")
        print(f"CTSI INGEST")
        print(f"  Tenant: {tenant.name} ({tenant_id})")
        print(f"  User:   {user.email} ({user_id})")
        print(f"{'=' * 60}\n")

        # ---- Load combined scrape data ----
        if not os.path.exists(COMBINED_FILE):
            print(f"[Ingest] ERROR: Combined data file not found: {COMBINED_FILE}")
            print("         Run 'scrape' command first to generate scraped data.")
            return

        with open(COMBINED_FILE, "r") as f:
            combined = json.load(f)

        facilities = combined.get("facilities", [])
        if not facilities:
            print("[Ingest] ERROR: No facilities found in combined data file.")
            return

        print(f"[Ingest] Loaded {len(facilities)} facilities from {COMBINED_FILE}")

        # ---- Collect all existing external_ids for this tenant + source_type ----
        existing_ids_rows = db.query(DBDocument.external_id).filter(
            DBDocument.tenant_id == tenant_id,
            DBDocument.source_type == "ctsi_scraper",
        ).all()
        existing_external_ids = {row[0] for row in existing_ids_rows}
        print(f"[Ingest] Found {len(existing_external_ids)} existing CTSI documents in DB")

        # ---- Phase 1: Create Document rows ----
        new_docs: list = []  # Will hold DBDocument instances after commit
        docs_skipped = 0
        docs_created = 0
        docs_in_batch = 0

        # --- 1a: CTSI facility pages (Level 2 data) ---
        print(f"\n[Ingest] Processing {len(facilities)} CTSI facility pages...")
        for facility in facilities:
            ctsi_url = facility.get("ctsi_url", "")
            full_text = facility.get("full_text", "")

            if not ctsi_url or not full_text:
                continue

            # Generate deterministic external_id
            ext_id = f"ctsi_{hashlib.md5(ctsi_url.encode()).hexdigest()}"

            if ext_id in existing_external_ids:
                docs_skipped += 1
                continue

            # Build content: combine description + full text
            name = facility.get("name", "Unknown Facility")
            description = facility.get("description", "")
            services_list = facility.get("services", [])

            # Build rich content
            content_parts = [f"# {name}\n"]
            if description:
                content_parts.append(f"{description}\n")
            if services_list:
                content_parts.append("\n## Services\n")
                for svc in services_list:
                    content_parts.append(f"- {svc}")
            content_parts.append(f"\n## Full Page Content\n{full_text}")
            content = "\n".join(content_parts)

            doc = DBDocument(
                tenant_id=tenant_id,
                external_id=ext_id,
                source_type="ctsi_scraper",
                title=f"CTSI: {name}",
                content=content,
                source_url=ctsi_url,
                doc_metadata={
                    "facility_name": name,
                    "slug": facility.get("slug", ""),
                    "primary_external_url": facility.get("primary_external_url"),
                    "services_count": len(services_list),
                    "scraped_at": facility.get("scraped_at"),
                    "source": "ctsi_level2",
                },
                status=DocumentStatus.CONFIRMED,
                classification=DocumentClassification.WORK,
                classification_confidence=1.0,
                classification_reason="Auto-classified: CTSI research core facility page",
            )
            db.add(doc)
            new_docs.append(doc)
            existing_external_ids.add(ext_id)
            docs_created += 1
            docs_in_batch += 1

            if docs_in_batch >= BATCH_SIZE:
                db.commit()
                print(f"[Ingest] Committed batch of {docs_in_batch} facility docs ({docs_created} total)")
                docs_in_batch = 0

        # Commit remaining facility docs
        if docs_in_batch > 0:
            db.commit()
            print(f"[Ingest] Committed final facility batch ({docs_created} total)")
            docs_in_batch = 0

        print(f"[Ingest] Facility pages: {docs_created} created, {docs_skipped} skipped (already exist)")

        # --- 1b: External crawl pages (Level 3 data) ---
        external_dir = os.path.join(OUTPUT_DIR, "external")
        ext_docs_created = 0
        ext_docs_skipped = 0

        if os.path.isdir(external_dir):
            crawl_files = [f for f in os.listdir(external_dir) if f.endswith("_crawl.json")]
            print(f"\n[Ingest] Processing {len(crawl_files)} external crawl files from {external_dir}...")

            for crawl_filename in crawl_files:
                crawl_filepath = os.path.join(external_dir, crawl_filename)
                try:
                    with open(crawl_filepath, "r") as f:
                        crawl_data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"[Ingest] WARNING: Could not read {crawl_filepath}: {e}")
                    continue

                facility_name = crawl_data.get("facility_name", "Unknown")
                source_url = crawl_data.get("source_url", "")
                pages = crawl_data.get("pages", [])

                for page in pages:
                    page_url = page.get("url", "")
                    page_content = page.get("content", "")
                    page_title = page.get("title", "")

                    if not page_url or not page_content:
                        continue

                    ext_id = f"ctsi_ext_{hashlib.md5(page_url.encode()).hexdigest()}"

                    if ext_id in existing_external_ids:
                        ext_docs_skipped += 1
                        continue

                    doc = DBDocument(
                        tenant_id=tenant_id,
                        external_id=ext_id,
                        source_type="ctsi_scraper",
                        title=page_title or f"External: {facility_name}",
                        content=page_content,
                        source_url=page_url,
                        doc_metadata={
                            "facility_name": facility_name,
                            "facility_slug": crawl_data.get("facility_slug", ""),
                            "crawl_source_url": source_url,
                            "scraped_at": crawl_data.get("crawled_at"),
                            "source": "ctsi_level3_external",
                        },
                        status=DocumentStatus.CONFIRMED,
                        classification=DocumentClassification.WORK,
                        classification_confidence=1.0,
                        classification_reason="Auto-classified: CTSI research core external site",
                    )
                    db.add(doc)
                    new_docs.append(doc)
                    existing_external_ids.add(ext_id)
                    ext_docs_created += 1
                    docs_in_batch += 1

                    if docs_in_batch >= BATCH_SIZE:
                        db.commit()
                        print(f"[Ingest] Committed batch of {docs_in_batch} external docs ({ext_docs_created} ext total)")
                        docs_in_batch = 0

            # Commit remaining external docs
            if docs_in_batch > 0:
                db.commit()
                print(f"[Ingest] Committed final external batch ({ext_docs_created} ext total)")
                docs_in_batch = 0

            print(f"[Ingest] External pages: {ext_docs_created} created, {ext_docs_skipped} skipped (already exist)")
        else:
            print(f"[Ingest] No external crawl directory found at {external_dir}, skipping Level 3 data.")

        total_created = docs_created + ext_docs_created
        total_skipped = docs_skipped + ext_docs_skipped

        print(f"\n[Ingest] Phase 1 complete: {total_created} new documents, {total_skipped} skipped")

        if total_created == 0:
            print("[Ingest] No new documents to process. Done!")
            return

        # ---- Phase 2: Extraction (structured summaries) ----
        print(f"\n{'=' * 60}")
        print(f"Phase 2: Extracting structured summaries for {total_created} documents")
        print(f"{'=' * 60}")

        try:
            extraction_service = get_extraction_service()

            def extraction_progress(cur, total, msg):
                if cur % 10 == 0 or cur == total:
                    print(f"[Ingest] Extraction progress: {cur}/{total} - {msg}")

            extract_result = extraction_service.extract_documents(
                documents=new_docs,
                db=db,
                force=False,
                progress_callback=extraction_progress,
            )
            print(f"[Ingest] Extraction complete: {extract_result.get('extracted', 0)} extracted, "
                  f"{extract_result.get('skipped', 0)} skipped, "
                  f"{extract_result.get('errors', 0)} errors")
        except Exception as e:
            print(f"[Ingest] EXTRACTION ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()
            print("[Ingest] Continuing to embedding phase despite extraction error...")

        # ---- Phase 3: Embedding ----
        print(f"\n{'=' * 60}")
        print(f"Phase 3: Embedding {total_created} documents")
        print(f"{'=' * 60}")

        try:
            embedding_service = get_embedding_service()

            def embedding_progress(cur, total, msg):
                if cur % 10 == 0 or cur == total:
                    print(f"[Ingest] Embedding progress: {cur}/{total} - {msg}")

            embed_result = embedding_service.embed_documents(
                documents=new_docs,
                tenant_id=tenant_id,
                db=db,
                force_reembed=False,
                progress_callback=embedding_progress,
            )
            print(f"[Ingest] Embedding complete: {embed_result.get('embedded', 0)} embedded, "
                  f"{embed_result.get('chunks', 0)} chunks, "
                  f"{embed_result.get('skipped', 0)} skipped")
            if embed_result.get('errors'):
                print(f"[Ingest] Embedding errors: {embed_result['errors']}")
        except Exception as e:
            print(f"[Ingest] EMBEDDING ERROR: {type(e).__name__}: {e}")
            traceback.print_exc()

        # ---- Summary ----
        print(f"\n{'=' * 60}")
        print(f"INGEST COMPLETE")
        print(f"  Facility pages created:  {docs_created}")
        print(f"  External pages created:  {ext_docs_created}")
        print(f"  Total new documents:     {total_created}")
        print(f"  Skipped (already exist): {total_skipped}")
        print(f"{'=' * 60}")

    except Exception as e:
        print(f"[Ingest] FATAL ERROR: {type(e).__name__}: {e}")
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point with argparse."""
    parser = argparse.ArgumentParser(
        description="UCLA CTSI Research Cores Scraper & Ingester",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m scripts.scrape_ctsi scrape
  python -m scripts.scrape_ctsi scrape --skip-firecrawl
  python -m scripts.scrape_ctsi scrape --max-firecrawl-pages 20
  python -m scripts.scrape_ctsi ingest
  python -m scripts.scrape_ctsi ingest --tenant-id abc123 --user-id user456
  python -m scripts.scrape_ctsi scrape+ingest
        """,
    )

    parser.add_argument(
        "command",
        choices=["scrape", "ingest", "scrape+ingest"],
        help="Command to run: scrape, ingest, or scrape+ingest",
    )
    parser.add_argument(
        "--max-firecrawl-pages",
        type=int,
        default=DEFAULT_MAX_FIRECRAWL_PAGES,
        help=f"Max pages to crawl per external site (default: {DEFAULT_MAX_FIRECRAWL_PAGES})",
    )
    parser.add_argument(
        "--skip-firecrawl",
        action="store_true",
        help="Skip Level 3 Firecrawl crawling of external sites",
    )
    parser.add_argument(
        "--tenant-id",
        type=str,
        default=None,
        help="Tenant ID for ingestion (optional; auto-detects first tenant if omitted)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="User ID for ingestion (optional; auto-detects first user if omitted)",
    )

    args = parser.parse_args()

    # Note: --tenant-id and --user-id are optional for ingest commands.
    # If not provided, run_ingest() will auto-detect from the first
    # tenant/user in the database.

    # Run commands
    if args.command == "scrape":
        run_scrape(
            skip_firecrawl=args.skip_firecrawl,
            max_firecrawl_pages=args.max_firecrawl_pages,
        )

    elif args.command == "ingest":
        run_ingest(tenant_id=args.tenant_id, user_id=args.user_id)

    elif args.command == "scrape+ingest":
        run_scrape(
            skip_firecrawl=args.skip_firecrawl,
            max_firecrawl_pages=args.max_firecrawl_pages,
        )
        run_ingest(tenant_id=args.tenant_id, user_id=args.user_id)


if __name__ == "__main__":
    main()
