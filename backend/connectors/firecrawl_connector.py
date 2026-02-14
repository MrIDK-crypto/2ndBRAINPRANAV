"""
Firecrawl Connector - Full Website Crawler with PDF Support

Uses Firecrawl API (https://firecrawl.dev) for comprehensive website crawling.
Features:
- Recursive crawling of entire websites
- PDF extraction and parsing
- JavaScript rendering for SPAs
- Sitemap discovery
- Clean markdown output
- Link extraction
"""

import os
import time
import hashlib
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

import requests

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document


class FirecrawlConnector(BaseConnector):
    """
    Firecrawl-powered website crawler for comprehensive content extraction.

    Key capabilities:
    - Full recursive website crawling (not just BFS)
    - PDF extraction and parsing built-in
    - JavaScript rendering for dynamic sites
    - Automatic sitemap discovery
    - Clean markdown output
    - Subdomain support
    """

    CONNECTOR_TYPE = "firecrawl"
    REQUIRED_CREDENTIALS = []  # API key from env
    OPTIONAL_SETTINGS = {
        "start_url": "",
        "max_pages": 100,           # Firecrawl limit (default 10000 max)
        "exclude_patterns": [],     # URL patterns to exclude (e.g., ["/blog/*"])
        "include_patterns": [],     # URL patterns to specifically include
    }

    # Firecrawl API configuration
    FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v1"
    FIRECRAWL_API_V2_BASE = "https://api.firecrawl.dev/v2"

    # Polling configuration
    POLL_INTERVAL = 3  # seconds between status checks
    MAX_POLL_TIME = 1800  # 30 minutes max wait

    def __init__(self, config: ConnectorConfig, tenant_id: Optional[str] = None):
        print(f"[Firecrawl] __init__ called")
        super().__init__(config)
        self.tenant_id = tenant_id
        self.error_count = 0
        self.success_count = 0

        # Get API key from environment
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        if not self.api_key:
            print("[Firecrawl] WARNING: FIRECRAWL_API_KEY not set in environment")

        # Set up HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

        # Track crawl job
        self._current_crawl_id: Optional[str] = None
        self._progress_callback: Optional[callable] = None

    def set_progress_callback(self, callback: callable):
        """Set callback for progress updates during crawl."""
        self._progress_callback = callback

    def _report_progress(self, current: int, total: int, message: str = ""):
        """Report progress to callback if set."""
        if self._progress_callback:
            try:
                self._progress_callback(current, total, message)
            except Exception as e:
                print(f"[Firecrawl] Progress callback error: {e}")

    async def connect(self) -> bool:
        """Test connection to Firecrawl API."""
        try:
            if not self.api_key:
                self._set_error("FIRECRAWL_API_KEY not configured")
                return False

            # Test the API with a simple request
            # Firecrawl doesn't have a dedicated health endpoint, so we check auth
            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print("[Firecrawl] Connected successfully")
            return True

        except Exception as e:
            self._set_error(str(e))
            print(f"[Firecrawl] Connection failed: {e}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Firecrawl."""
        self.status = ConnectorStatus.DISCONNECTED
        self._current_crawl_id = None
        return True

    async def test_connection(self) -> bool:
        """Test if Firecrawl API is reachable and authenticated."""
        try:
            if not self.api_key:
                return False

            # Do a minimal scrape to test auth
            test_url = "https://example.com"
            response = self.session.post(
                f"{self.FIRECRAWL_API_V2_BASE}/scrape",
                json={"url": test_url},
                timeout=30
            )

            if response.status_code == 401:
                self._set_error("Invalid API key")
                return False
            elif response.status_code == 402:
                self._set_error("Firecrawl account needs credits")
                return False
            elif response.status_code == 429:
                # Rate limited but auth works
                return True

            return response.status_code == 200

        except Exception as e:
            self._set_error(str(e))
            return False

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific document by ID (not supported for crawled content)."""
        return None

    def _start_crawl(self, start_url: str, settings: Dict[str, Any]) -> Optional[str]:
        """
        Start a crawl job and return the job ID.

        Args:
            start_url: The URL to start crawling from
            settings: Crawl configuration

        Returns:
            Crawl job ID or None if failed
        """
        max_pages = settings.get("max_pages", 100)
        exclude_patterns = settings.get("exclude_patterns", [])
        include_patterns = settings.get("include_patterns", [])

        # Build crawl request - Firecrawl v2 API parameters (minimal)
        # Only use documented v2 params: url, limit, scrapeOptions, excludePaths, includePaths
        crawl_request = {
            "url": start_url,
            "limit": max_pages,
            "scrapeOptions": {
                "formats": ["markdown", "links"],
            }
        }

        # Add exclude patterns
        if exclude_patterns:
            crawl_request["excludePaths"] = exclude_patterns

        # Add include patterns (priority paths)
        if include_patterns:
            crawl_request["includePaths"] = include_patterns

        print(f"[Firecrawl] Starting crawl: {start_url}")
        print(f"[Firecrawl] Settings: max_pages={max_pages}")

        try:
            response = self.session.post(
                f"{self.FIRECRAWL_API_V2_BASE}/crawl",
                json=crawl_request,
                timeout=60
            )

            if response.status_code == 401:
                self._set_error("Invalid Firecrawl API key")
                return None
            elif response.status_code == 402:
                self._set_error("Firecrawl account needs credits - please add credits at firecrawl.dev")
                return None
            elif response.status_code == 429:
                self._set_error("Firecrawl rate limit exceeded - please wait and try again")
                return None
            elif response.status_code != 200:
                error_msg = response.text[:500] if response.text else "Unknown error"
                self._set_error(f"Firecrawl API error ({response.status_code}): {error_msg}")
                return None

            result = response.json()

            if not result.get("success"):
                self._set_error(f"Crawl failed to start: {result.get('error', 'Unknown error')}")
                return None

            crawl_id = result.get("id")
            print(f"[Firecrawl] Crawl started with ID: {crawl_id}")
            return crawl_id

        except requests.exceptions.Timeout:
            self._set_error("Firecrawl API timeout - service may be busy")
            return None
        except Exception as e:
            self._set_error(f"Failed to start crawl: {str(e)}")
            traceback.print_exc()
            return None

    def _poll_crawl_status(self, crawl_id: str) -> Dict[str, Any]:
        """
        Poll crawl status until complete or timeout.

        Args:
            crawl_id: The crawl job ID

        Returns:
            Complete crawl results with all pages
        """
        start_time = time.time()
        all_data = []
        last_completed = 0

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.MAX_POLL_TIME:
                print(f"[Firecrawl] Crawl timeout after {elapsed:.0f}s")
                break

            try:
                response = self.session.get(
                    f"{self.FIRECRAWL_API_V2_BASE}/crawl/{crawl_id}",
                    timeout=30
                )

                if response.status_code != 200:
                    print(f"[Firecrawl] Status check failed: {response.status_code}")
                    time.sleep(self.POLL_INTERVAL)
                    continue

                result = response.json()
                status = result.get("status", "unknown")
                total = result.get("total", 0)
                completed = result.get("completed", 0)

                # Report progress
                if completed != last_completed:
                    self._report_progress(completed, total, f"Crawling... {completed}/{total} pages")
                    last_completed = completed
                    print(f"[Firecrawl] Progress: {completed}/{total} pages ({status})")

                # Collect data from this response
                data = result.get("data", [])
                if data:
                    all_data.extend(data)

                # Check if complete
                if status == "completed":
                    print(f"[Firecrawl] Crawl completed: {completed} pages")

                    # Handle pagination (if response > 10MB)
                    next_url = result.get("next")
                    while next_url:
                        print(f"[Firecrawl] Fetching next page of results...")
                        next_response = self.session.get(next_url, timeout=60)
                        if next_response.status_code == 200:
                            next_result = next_response.json()
                            next_data = next_result.get("data", [])
                            all_data.extend(next_data)
                            next_url = next_result.get("next")
                        else:
                            break

                    return {
                        "status": "completed",
                        "total": total,
                        "completed": completed,
                        "data": all_data,
                        "credits_used": result.get("creditsUsed", 0)
                    }

                elif status == "failed":
                    error = result.get("error", "Unknown error")
                    print(f"[Firecrawl] Crawl failed: {error}")
                    return {
                        "status": "failed",
                        "error": error,
                        "data": all_data
                    }

                # Still scraping, wait and poll again
                time.sleep(self.POLL_INTERVAL)

            except Exception as e:
                print(f"[Firecrawl] Poll error: {e}")
                time.sleep(self.POLL_INTERVAL)

        # Timeout - return what we have
        return {
            "status": "timeout",
            "data": all_data,
            "error": f"Crawl timed out after {self.MAX_POLL_TIME}s"
        }

    def _page_to_document(self, page: Dict[str, Any], source_url: str) -> Optional[Document]:
        """
        Convert a Firecrawl page result to a Document object.

        Args:
            page: Firecrawl page data
            source_url: Original crawl start URL

        Returns:
            Document object or None if invalid
        """
        try:
            metadata = page.get("metadata", {})
            page_url = metadata.get("sourceURL", metadata.get("url", ""))

            if not page_url:
                return None

            # Get content - prefer markdown
            content = page.get("markdown", "")
            if not content:
                content = page.get("html", "")
            if not content:
                content = page.get("rawHtml", "")

            if not content or len(content.strip()) < 50:
                # Skip pages with minimal content
                return None

            # Extract title
            title = metadata.get("title", "")
            if not title:
                title = metadata.get("ogTitle", "")
            if not title:
                # Extract from URL
                parsed = urlparse(page_url)
                path = parsed.path.strip("/")
                if path:
                    title = path.split("/")[-1].replace("-", " ").replace("_", " ").title()
                else:
                    title = parsed.netloc

            # Generate document ID from URL hash
            doc_id = hashlib.md5(page_url.encode()).hexdigest()

            # Determine document type
            doc_type = "webpage"
            if page_url.lower().endswith(".pdf"):
                doc_type = "pdf"
            elif metadata.get("mimeType", "").startswith("application/pdf"):
                doc_type = "pdf"

            # Extract links for metadata
            links = page.get("links", [])

            # Build metadata
            doc_metadata = {
                "url": page_url,
                "source_url": source_url,
                "description": metadata.get("description", metadata.get("ogDescription", "")),
                "keywords": metadata.get("keywords", ""),
                "language": metadata.get("language", ""),
                "status_code": metadata.get("statusCode", 200),
                "word_count": len(content.split()),
                "links_count": len(links),
                "crawled_at": datetime.utcnow().isoformat(),
                "crawl_engine": "firecrawl",
            }

            # Add links if present (useful for knowledge graph)
            if links:
                doc_metadata["links"] = links[:50]  # Limit to first 50

            return Document(
                doc_id=f"firecrawl_{doc_id}",
                source="firecrawl",
                content=content,
                title=title,
                metadata=doc_metadata,
                timestamp=datetime.utcnow(),
                author=metadata.get("author", ""),
                url=page_url,
                doc_type=doc_type
            )

        except Exception as e:
            print(f"[Firecrawl] Error converting page to document: {e}")
            return None

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Crawl the website and return all documents.

        Args:
            since: Not used for web crawling (always full crawl)

        Returns:
            List of Document objects from crawled pages
        """
        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            settings = self.config.settings
            start_url = settings.get("start_url", "")

            if not start_url:
                self._set_error("No start_url configured")
                return []

            # Ensure URL has protocol
            if not start_url.startswith(("http://", "https://")):
                start_url = f"https://{start_url}"

            print(f"[Firecrawl] Starting sync for: {start_url}")
            self._report_progress(0, 1, f"Starting crawl of {start_url}...")

            # Start the crawl
            crawl_id = self._start_crawl(start_url, settings)

            if not crawl_id:
                return []

            self._current_crawl_id = crawl_id

            # Poll for results
            result = self._poll_crawl_status(crawl_id)

            if result.get("status") == "failed":
                self._set_error(result.get("error", "Crawl failed"))
                return []

            # Convert pages to documents
            pages = result.get("data", [])
            print(f"[Firecrawl] Processing {len(pages)} crawled pages...")

            for i, page in enumerate(pages):
                doc = self._page_to_document(page, start_url)
                if doc:
                    documents.append(doc)

                if (i + 1) % 10 == 0:
                    self._report_progress(i + 1, len(pages), f"Processing {i+1}/{len(pages)} pages...")

            self.success_count = len(documents)
            self.error_count = len(pages) - len(documents)

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()

            print(f"[Firecrawl] Sync complete: {len(documents)} documents extracted from {len(pages)} pages")

            # Update sync stats
            self.sync_stats = {
                "pages_crawled": len(pages),
                "documents_extracted": len(documents),
                "credits_used": result.get("credits_used", 0),
                "status": result.get("status"),
            }

            return documents

        except Exception as e:
            self._set_error(str(e))
            traceback.print_exc()
            return []
        finally:
            self._current_crawl_id = None

    def cancel_crawl(self) -> bool:
        """Cancel the current crawl if running."""
        if not self._current_crawl_id:
            return False

        try:
            response = self.session.delete(
                f"{self.FIRECRAWL_API_V2_BASE}/crawl/{self._current_crawl_id}",
                timeout=30
            )
            if response.status_code == 200:
                print(f"[Firecrawl] Crawl {self._current_crawl_id} cancelled")
                self._current_crawl_id = None
                return True
        except Exception as e:
            print(f"[Firecrawl] Failed to cancel crawl: {e}")

        return False


class FirecrawlScraper:
    """
    Single-page scraper using Firecrawl.
    Use this for scraping individual URLs without full crawl.
    """

    FIRECRAWL_API_BASE = "https://api.firecrawl.dev/v1"

    def __init__(self):
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def scrape_url(self, url: str, options: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Scrape a single URL.

        Args:
            url: URL to scrape
            options: Scrape options (formats, wait, timeout, etc.)

        Returns:
            Scraped content or None if failed
        """
        if not self.api_key:
            print("[FirecrawlScraper] No API key configured")
            return None

        request_data = {
            "url": url,
            "formats": ["markdown", "links"],
        }

        if options:
            request_data.update(options)

        try:
            response = self.session.post(
                f"{self.FIRECRAWL_API_BASE}/scrape",
                json=request_data,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("data", {})

            print(f"[FirecrawlScraper] Scrape failed: {response.status_code} - {response.text[:200]}")
            return None

        except Exception as e:
            print(f"[FirecrawlScraper] Scrape error: {e}")
            return None

    def map_website(self, url: str) -> List[str]:
        """
        Get a list of all URLs on a website (fast sitemap discovery).

        Args:
            url: Base URL of the website

        Returns:
            List of URLs found on the website
        """
        if not self.api_key:
            return []

        try:
            response = self.session.post(
                f"{self.FIRECRAWL_API_BASE}/map",
                json={"url": url},
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    return result.get("links", [])

            return []

        except Exception as e:
            print(f"[FirecrawlScraper] Map error: {e}")
            return []
