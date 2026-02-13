"""
GitHub Connector
OAuth integration and repository code analysis for 2nd Brain.
"""

import os
import re
import requests
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone
import base64

from connectors.base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document


class GitHubConnector(BaseConnector):
    """
    Handle GitHub OAuth and repository access.

    Features:
    - OAuth 2.0 flow
    - Repository listing
    - Code file fetching
    - Smart filtering (code files only)
    - Rate limit handling
    - LLM-powered code analysis
    """

    CONNECTOR_TYPE = "github"

    def __init__(self, config_or_token: Union[ConnectorConfig, str, None] = None, access_token: Optional[str] = None):
        """
        Initialize GitHub connector.

        Args:
            config_or_token: Either a ConnectorConfig object or an access token string (for backward compatibility)
            access_token: GitHub OAuth access token (deprecated, use config_or_token)
        """
        # Handle backward compatibility
        if isinstance(config_or_token, ConnectorConfig):
            super().__init__(config_or_token)
            self.access_token = config_or_token.credentials.get('access_token')
        elif isinstance(config_or_token, str):
            # Legacy: access_token passed directly
            dummy_config = ConnectorConfig(
                connector_type='github',
                user_id='legacy',
                credentials={'access_token': config_or_token}
            )
            super().__init__(dummy_config)
            self.access_token = config_or_token
        elif access_token:
            # Legacy: access_token as keyword argument
            dummy_config = ConnectorConfig(
                connector_type='github',
                user_id='legacy',
                credentials={'access_token': access_token}
            )
            super().__init__(dummy_config)
            self.access_token = access_token
        else:
            dummy_config = ConnectorConfig(
                connector_type='github',
                user_id='legacy',
                credentials={}
            )
            super().__init__(dummy_config)
            self.access_token = None

        self.client_id = os.getenv('GITHUB_CLIENT_ID')
        self.client_secret = os.getenv('GITHUB_CLIENT_SECRET')
        self.redirect_uri = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:5003/api/integrations/github/callback')

        self.base_url = 'https://api.github.com'
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        if self.access_token:
            self.headers['Authorization'] = f'Bearer {self.access_token}'
            self.status = ConnectorStatus.CONNECTED

    # =========================================================================
    # OAUTH FLOW
    # =========================================================================

    def get_authorization_url(self, state: str) -> str:
        """
        Get GitHub OAuth authorization URL.

        Args:
            state: CSRF protection state

        Returns:
            Authorization URL to redirect user to
        """
        scopes = ['repo', 'read:user', 'read:org']
        scope_string = ' '.join(scopes)

        return (
            f"https://github.com/login/oauth/authorize?"
            f"client_id={self.client_id}&"
            f"redirect_uri={self.redirect_uri}&"
            f"scope={scope_string}&"
            f"state={state}"
        )

    def exchange_code_for_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.

        Args:
            code: Authorization code from GitHub

        Returns:
            {
                'access_token': '...',
                'token_type': 'bearer',
                'scope': 'repo,read:user'
            }
        """
        response = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'redirect_uri': self.redirect_uri
            }
        )

        response.raise_for_status()
        data = response.json()

        if 'error' in data:
            raise Exception(f"GitHub OAuth error: {data.get('error_description', data['error'])}")

        return data

    # =========================================================================
    # USER & REPOSITORY INFO
    # =========================================================================

    def get_user_info(self) -> Dict:
        """
        Get authenticated user information.

        Returns:
            {
                'login': 'username',
                'id': 12345,
                'name': 'Full Name',
                'email': 'user@example.com',
                'avatar_url': '...',
                'public_repos': 10,
                'total_private_repos': 5
            }
        """
        response = requests.get(
            f'{self.base_url}/user',
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()

    def get_repositories(self, per_page: int = 100) -> List[Dict]:
        """
        Get all repositories accessible to user.

        Args:
            per_page: Results per page (max 100)

        Returns:
            List of repository dicts with:
            - id, name, full_name
            - description, language
            - private, fork, archived
            - default_branch, size
            - created_at, updated_at, pushed_at
        """
        repos = []
        page = 1

        while True:
            response = requests.get(
                f'{self.base_url}/user/repos',
                headers=self.headers,
                params={
                    'per_page': per_page,
                    'page': page,
                    'sort': 'updated',
                    'affiliation': 'owner,collaborator,organization_member'
                }
            )
            response.raise_for_status()

            batch = response.json()
            if not batch:
                break

            repos.extend(batch)

            # Check if more pages
            if len(batch) < per_page:
                break

            page += 1

        return repos

    # =========================================================================
    # CODE FETCHING
    # =========================================================================

    # Code file extensions to analyze
    CODE_EXTENSIONS = {
        # Backend
        '.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rb', '.php',
        '.cs', '.cpp', '.c', '.h', '.hpp', '.rs', '.kt', '.swift', '.scala',

        # Frontend
        '.html', '.css', '.scss', '.sass', '.less', '.vue', '.svelte',

        # Config & Infrastructure
        '.yaml', '.yml', '.json', '.toml', '.ini', '.conf',
        '.tf', '.tfvars',  # Terraform

        # Documentation
        '.md', '.rst', '.txt',

        # Database
        '.sql',

        # Scripts
        '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat',

        # Data Science & Notebooks
        '.ipynb',  # Jupyter notebooks
        '.r', '.R',  # R scripts
    }

    # Directories to skip
    SKIP_DIRS = {
        'node_modules', 'venv', 'env', '.venv', '__pycache__', 'dist', 'build',
        '.git', '.svn', '.hg', 'vendor', 'tmp', 'temp', 'cache', '.cache',
        'coverage', '.coverage', '.pytest_cache', '.mypy_cache', '.tox',
        'logs', 'log', '.DS_Store', 'target', 'out', '.next', '.nuxt'
    }

    def get_repository_tree(self, owner: str, repo: str, branch: str = 'main') -> List[Dict]:
        """
        Get repository file tree recursively.

        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name (default: main)

        Returns:
            List of file dicts with:
            - path, type (blob/tree), sha, size, url
        """
        try:
            response = requests.get(
                f'{self.base_url}/repos/{owner}/{repo}/git/trees/{branch}',
                headers=self.headers,
                params={'recursive': '1'}
            )
            response.raise_for_status()

            data = response.json()
            return data.get('tree', [])

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                # Try 'master' branch
                response = requests.get(
                    f'{self.base_url}/repos/{owner}/{repo}/git/trees/master',
                    headers=self.headers,
                    params={'recursive': '1'}
                )
                response.raise_for_status()
                data = response.json()
                return data.get('tree', [])
            raise

    def filter_code_files(self, tree: List[Dict], max_files: int = 500) -> List[Dict]:
        """
        Filter tree to only code files (skip binaries, dependencies, etc.).

        Args:
            tree: Repository tree from get_repository_tree()
            max_files: Maximum files to return

        Returns:
            Filtered list of code files sorted by relevance
        """
        code_files = []

        for item in tree:
            # Only process files (blobs), not directories
            if item['type'] != 'blob':
                continue

            path = item['path']

            # Skip files in ignored directories
            path_parts = path.split('/')
            if any(part in self.SKIP_DIRS for part in path_parts):
                continue

            # Check file extension
            _, ext = os.path.splitext(path.lower())
            if ext not in self.CODE_EXTENSIONS:
                continue

            # Skip very large files (>1MB)
            if item.get('size', 0) > 1_000_000:
                continue

            code_files.append(item)

        # Prioritize important files
        def priority_score(item):
            path = item['path'].lower()
            score = 0

            # Boost important files
            if 'readme' in path:
                score += 1000
            if path.endswith('.md'):
                score += 100
            if 'config' in path or 'settings' in path:
                score += 50
            if path.endswith(('.py', '.js', '.ts', '.go', '.java')):
                score += 10

            # Penalize test files (but don't skip)
            if 'test' in path or 'spec' in path:
                score -= 5

            return -score  # Negative for reverse sort

        code_files.sort(key=priority_score)

        return code_files[:max_files]

    def get_file_content(self, owner: str, repo: str, path: str) -> Optional[str]:
        """
        Get file content from GitHub.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository

        Returns:
            File content as string, or None if binary/error
        """
        try:
            response = requests.get(
                f'{self.base_url}/repos/{owner}/{repo}/contents/{path}',
                headers=self.headers
            )
            response.raise_for_status()

            data = response.json()

            # GitHub returns content as base64
            if 'content' in data:
                content_b64 = data['content']
                content_bytes = base64.b64decode(content_b64)

                # Try to decode as UTF-8 (skip binary files)
                try:
                    return content_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    return None

            return None

        except Exception as e:
            print(f"[GitHub] Error fetching {path}: {e}")
            return None

    def fetch_repository_code(
        self,
        owner: str,
        repo: str,
        max_files: int = 100,
        max_chars_per_file: int = 50000
    ) -> List[Dict]:
        """
        Fetch code files from repository with content.

        Args:
            owner: Repository owner
            repo: Repository name
            max_files: Maximum files to fetch
            max_chars_per_file: Max characters per file

        Returns:
            List of dicts:
            {
                'path': 'src/main.py',
                'content': '...',
                'language': 'Python',
                'size': 1234,
                'lines': 50
            }
        """
        print(f"[GitHub] Fetching repository tree: {owner}/{repo}")
        tree = self.get_repository_tree(owner, repo)

        print(f"[GitHub] Found {len(tree)} total items in repository")
        code_files = self.filter_code_files(tree, max_files=max_files)

        print(f"[GitHub] Filtered to {len(code_files)} code files")

        results = []

        for i, file_item in enumerate(code_files, 1):
            path = file_item['path']
            print(f"[GitHub] [{i}/{len(code_files)}] Fetching: {path}")

            content = self.get_file_content(owner, repo, path)

            if content is None:
                print(f"[GitHub]   → Skipped (binary or error)")
                continue

            # Truncate if too long
            if len(content) > max_chars_per_file:
                content = content[:max_chars_per_file] + "\n\n[... truncated ...]"

            # Detect language from extension
            _, ext = os.path.splitext(path)
            language = self._extension_to_language(ext)

            results.append({
                'path': path,
                'content': content,
                'language': language,
                'size': file_item.get('size', len(content)),
                'lines': content.count('\n') + 1
            })

        print(f"[GitHub] Successfully fetched {len(results)} files")
        return results

    @staticmethod
    def _extension_to_language(ext: str) -> str:
        """Map file extension to language name"""
        mapping = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.jsx': 'React JSX',
            '.tsx': 'React TSX',
            '.java': 'Java',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.cs': 'C#',
            '.cpp': 'C++',
            '.c': 'C',
            '.h': 'C/C++ Header',
            '.rs': 'Rust',
            '.kt': 'Kotlin',
            '.swift': 'Swift',
            '.scala': 'Scala',
            '.html': 'HTML',
            '.css': 'CSS',
            '.scss': 'SCSS',
            '.yaml': 'YAML',
            '.yml': 'YAML',
            '.json': 'JSON',
            '.md': 'Markdown',
            '.sql': 'SQL',
            '.sh': 'Shell',
            '.bash': 'Bash',
            '.ipynb': 'Jupyter Notebook',
            '.r': 'R',
        }
        return mapping.get(ext.lower(), 'Unknown')

    # =========================================================================
    # RATE LIMIT HANDLING
    # =========================================================================

    def get_rate_limit(self) -> Dict:
        """
        Get current rate limit status.

        Returns:
            {
                'limit': 5000,
                'remaining': 4999,
                'reset': 1234567890  # Unix timestamp
            }
        """
        response = requests.get(
            f'{self.base_url}/rate_limit',
            headers=self.headers
        )
        response.raise_for_status()

        data = response.json()
        return data['resources']['core']

    # =========================================================================
    # BASE CONNECTOR INTERFACE IMPLEMENTATION
    # =========================================================================

    async def connect(self) -> bool:
        """
        Establish connection to GitHub.
        Returns True if successful, False otherwise.
        """
        if not self.access_token:
            self.status = ConnectorStatus.ERROR
            self.last_error = "No access token provided"
            return False

        try:
            self.status = ConnectorStatus.CONNECTING
            # Test the connection by getting user info
            user_info = self.get_user_info()
            if user_info and user_info.get('login'):
                self.status = ConnectorStatus.CONNECTED
                return True
            else:
                self.status = ConnectorStatus.ERROR
                self.last_error = "Failed to get user info"
                return False
        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            return False

    async def disconnect(self) -> bool:
        """
        Disconnect from GitHub.
        """
        self.status = ConnectorStatus.DISCONNECTED
        self.access_token = None
        self.headers.pop('Authorization', None)
        return True

    async def test_connection(self) -> bool:
        """
        Test if the connection is valid.
        """
        try:
            user_info = self.get_user_info()
            return user_info is not None and 'login' in user_info
        except Exception:
            return False

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a specific document by ID.
        GitHub connector doesn't support fetching individual documents after sync.
        """
        # GitHub documents are created during sync and stored in the database
        # This method would require database access which the connector doesn't have
        return None

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync and analyze GitHub repository code.

        This method:
        1. Gets the most recently updated repository (or uses configured repo)
        2. Fetches code files from the repository
        3. Analyzes the code using LLM (CodeAnalysisService)
        4. Returns Document objects containing the analysis

        Args:
            since: Optional datetime to filter repositories updated after this time

        Returns:
            List of Document objects containing:
            - Technical documentation
            - Repository overview
            - Individual file analyses
        """
        if not self.access_token:
            self.last_error = "No access token"
            return []

        try:
            self.status = ConnectorStatus.SYNCING
            documents = []

            # Get configured repository or most recent one
            repository = self.config.settings.get('repository') if self.config else None

            if not repository:
                print("[GitHub] No repository configured, fetching most recent repo")
                repos = self.get_repositories()
                if not repos:
                    self.last_error = "No repositories found"
                    self.status = ConnectorStatus.CONNECTED
                    return []

                # Sort by updated_at and get most recent
                repos.sort(key=lambda r: r.get('updated_at', ''), reverse=True)
                repository = repos[0]['full_name']
                print(f"[GitHub] Auto-selected most recent repository: {repository}")

            if not repository or '/' not in repository:
                self.last_error = f"Invalid repository format: {repository}"
                self.status = ConnectorStatus.ERROR
                return []

            owner, repo = repository.split('/', 1)

            # Fetch repository code
            max_files = self.config.settings.get('max_files', 100) if self.config else 100
            max_files_to_analyze = self.config.settings.get('max_files_to_analyze', 5) if self.config else 5

            print(f"[GitHub] Fetching code from {repository}")
            code_files = self.fetch_repository_code(
                owner=owner,
                repo=repo,
                max_files=max_files
            )

            if not code_files:
                self.last_error = "No code files found in repository"
                self.status = ConnectorStatus.CONNECTED
                return []

            # Get repository info for description
            repos = self.get_repositories()
            repo_info = next(
                (r for r in repos if r['full_name'].lower() == repository.lower()),
                None
            )
            repo_description = repo_info['description'] if repo_info else None
            github_user = self.config.settings.get('github_user', 'unknown') if self.config else 'unknown'

            # Analyze repository with LLM
            print(f"[GitHub] Analyzing repository with LLM")
            try:
                from services.code_analysis_service import CodeAnalysisService
                analyzer = CodeAnalysisService()
                analysis = analyzer.analyze_repository(
                    repo_name=repository,
                    repo_description=repo_description,
                    code_files=code_files,
                    max_files_to_analyze=max_files_to_analyze
                )
            except Exception as e:
                print(f"[GitHub] LLM analysis failed: {e}, falling back to basic sync")
                # Fall back to basic file sync without analysis
                analysis = self._create_basic_analysis(repository, code_files, repo_description)

            # Create Document objects

            # 1. Main documentation document
            doc_main = Document(
                doc_id=f"github_{repository.replace('/', '_')}_docs",
                source="github",
                content=analysis.get('documentation', ''),
                title=f"{repository} - Technical Documentation",
                metadata={
                    'repository': repository,
                    'analysis_type': 'comprehensive_documentation',
                    'stats': analysis.get('stats', {})
                },
                timestamp=datetime.now(timezone.utc),
                author=github_user,
                url=f"https://github.com/{repository}",
                doc_type="code"
            )
            documents.append(doc_main)

            # 2. Repository overview document
            overview = analysis.get('repository_overview', {})
            overview_content = f"""# {repository} - Repository Overview

## Purpose
{overview.get('purpose', 'N/A')}

## Architecture
{overview.get('architecture', 'N/A')}

## Technology Stack
{chr(10).join(f'- {tech}' for tech in overview.get('tech_stack', []))}

## Design Patterns
{chr(10).join(f'- {pattern}' for pattern in overview.get('patterns', []))}

## Statistics
- Total Files: {analysis.get('stats', {}).get('total_files', 0)}
- Analyzed Files: {analysis.get('stats', {}).get('analyzed_files', 0)}
- Total Lines: {analysis.get('stats', {}).get('total_lines', 0):,}
"""

            doc_overview = Document(
                doc_id=f"github_{repository.replace('/', '_')}_overview",
                source="github",
                content=overview_content,
                title=f"{repository} - Overview",
                metadata={
                    'repository': repository,
                    'analysis_type': 'overview',
                    'overview': overview
                },
                timestamp=datetime.now(timezone.utc),
                author=github_user,
                url=f"https://github.com/{repository}",
                doc_type="code"
            )
            documents.append(doc_overview)

            # 3. Create a document for EVERY code file with actual content
            # This ensures all code files appear in the documents tab
            print(f"[GitHub] Creating documents for {len(code_files)} code files")
            for i, code_file in enumerate(code_files):
                file_path = code_file.get('path', 'Unknown file')
                file_content = code_file.get('content', '')
                file_language = code_file.get('language', 'Unknown')
                file_lines = code_file.get('lines', 0)

                # Find any LLM analysis for this file (if available)
                file_analysis = next(
                    (fa for fa in analysis.get('file_analyses', []) if fa.get('file_path') == file_path),
                    None
                )

                # Build document content: raw code + optional analysis
                if file_analysis:
                    doc_content = f"""# {file_path}

## Analysis Summary
{file_analysis.get('summary', 'No summary available')}

## Key Functions/Classes
{chr(10).join(f'- {func}' for func in file_analysis.get('key_functions', []))}

## Dependencies
{chr(10).join(f'- {dep}' for dep in file_analysis.get('dependencies', []))}

## Business Logic
{file_analysis.get('business_logic', '')}

---

## Source Code ({file_language}, {file_lines} lines)

```{file_language.lower()}
{file_content}
```
"""
                else:
                    # No LLM analysis, just include the raw code
                    doc_content = f"""# {file_path}

**Language:** {file_language}
**Lines:** {file_lines}

## Source Code

```{file_language.lower()}
{file_content}
```
"""

                doc_file = Document(
                    doc_id=f"github_{repository.replace('/', '_')}_{file_path.replace('/', '_')}",
                    source="github",
                    content=doc_content,
                    title=f"{repository} - {file_path}",
                    metadata={
                        'repository': repository,
                        'file_path': file_path,
                        'language': file_language,
                        'lines': file_lines,
                        'has_analysis': file_analysis is not None
                    },
                    timestamp=datetime.now(timezone.utc),
                    author=github_user,
                    url=f"https://github.com/{repository}/blob/main/{file_path}",
                    doc_type="code"
                )
                documents.append(doc_file)

                if (i + 1) % 20 == 0:
                    print(f"[GitHub] Created {i + 1}/{len(code_files)} file documents")

            # Update sync stats
            self.sync_stats = {
                'repository': repository,
                'documents_synced': len(documents),
                'files_analyzed': len(analysis.get('file_analyses', [])),
                'sync_time': datetime.now(timezone.utc).isoformat()
            }

            self.status = ConnectorStatus.CONNECTED
            print(f"[GitHub] Sync complete: {len(documents)} documents created")
            return documents

        except Exception as e:
            self.status = ConnectorStatus.ERROR
            self.last_error = str(e)
            print(f"[GitHub] Sync error: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _create_basic_analysis(self, repository: str, code_files: List[Dict], repo_description: Optional[str]) -> Dict:
        """
        Create a basic analysis without LLM when CodeAnalysisService is unavailable.
        """
        # Aggregate stats
        total_lines = sum(f.get('lines', 0) for f in code_files)
        languages = {}
        for f in code_files:
            lang = f.get('language', 'Unknown')
            languages[lang] = languages.get(lang, 0) + 1

        # Create basic overview
        file_analyses = []
        for f in code_files[:10]:
            file_analyses.append({
                'file_path': f.get('path', 'unknown'),
                'language': f.get('language', 'Unknown'),
                'summary': f'File with {f.get("lines", 0)} lines of {f.get("language", "code")}',
                'key_functions': [],
                'dependencies': [],
                'business_logic': 'See file content for details'
            })

        return {
            'documentation': f"# {repository}\n\n{repo_description or 'No description'}\n\nThis repository contains {len(code_files)} code files.",
            'repository_overview': {
                'purpose': repo_description or 'Repository purpose not described',
                'architecture': 'Architecture analysis requires LLM',
                'tech_stack': list(languages.keys()),
                'patterns': [],
                'components': {}
            },
            'stats': {
                'total_files': len(code_files),
                'analyzed_files': len(file_analyses),
                'total_lines': total_lines,
                'languages': languages
            },
            'file_analyses': file_analyses,
            'analyzed_at': datetime.now(timezone.utc).isoformat()
        }
