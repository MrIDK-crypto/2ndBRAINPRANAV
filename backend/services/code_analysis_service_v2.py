"""
Code Analysis Service V2 - Function-level LLM analysis with diagram generation

Replaces the old file-level analysis with:
1. tree-sitter parsing (every function/class extracted)
2. LLM explains each function/class individually (batched for efficiency)
3. Generates Mermaid diagrams from parsed structure
4. Produces embeddable docstrings for each code unit

This is the "Greptile trick" — embed explanations, not raw code.
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from openai import AzureOpenAI

from azure_openai_config import (
    AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT,
    AZURE_CHAT_DEPLOYMENT, AZURE_API_VERSION
)
from services.code_parser_service import CodeParserService, ParsedFile, CodeUnit


class CodeAnalysisServiceV2:
    """
    Analyze code at the function/class level using tree-sitter + LLM.

    Pipeline:
    1. Parse all files with tree-sitter → functions, classes, imports
    2. Batch-explain each code unit with LLM
    3. Generate Mermaid diagrams from structure
    4. Return structured documents ready for embedding
    """

    # Max code units to explain per LLM call (batching)
    BATCH_SIZE = 5
    # Max tokens per explanation
    MAX_EXPLANATION_TOKENS = 300
    # Max code chars to send per unit (truncate huge functions)
    MAX_CODE_PER_UNIT = 8000
    # Max total units to explain (budget control)
    MAX_UNITS_TO_EXPLAIN = 500

    def __init__(self):
        self.client = AzureOpenAI(
            api_key=AZURE_OPENAI_API_KEY,
            api_version=AZURE_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT
        )
        self.parser = CodeParserService()

    # =========================================================================
    # MAIN PIPELINE
    # =========================================================================

    def analyze_repository(
        self,
        repo_name: str,
        repo_description: Optional[str],
        code_files: List[Dict],
        max_files_to_analyze: int = None,  # Ignored — we analyze ALL files
    ) -> Dict:
        """
        Complete repository analysis pipeline (V2).

        Same interface as V1 for backward compatibility, but now:
        - Parses ALL files with tree-sitter
        - Explains every function/class
        - Generates Mermaid diagrams

        Args:
            repo_name: Repository name
            repo_description: Repository description
            code_files: List from GitHubConnector.fetch_repository_code()
            max_files_to_analyze: Ignored (kept for API compat)

        Returns:
            Same structure as V1 plus new fields:
            {
                'repository_overview': {...},
                'file_analyses': [{...}],
                'documentation': 'Markdown',
                'code_units': [{...}],          # NEW: per-function explanations
                'diagrams': [{...}],             # NEW: Mermaid diagrams
                'analyzed_at': '...',
                'stats': {...}
            }
        """
        print(f"[CodeAnalysisV2] Starting analysis: {repo_name} ({len(code_files)} files)")

        # Stage 1: Parse ALL files with tree-sitter
        print(f"[CodeAnalysisV2] Stage 1: Parsing {len(code_files)} files with tree-sitter...")
        parsed_files = self.parser.parse_files(code_files)

        total_units = sum(pf.total_units for pf in parsed_files)
        print(f"[CodeAnalysisV2] Parsed {total_units} code units from {len(parsed_files)} files")

        # Stage 2: Generate repository overview (1 LLM call)
        print(f"[CodeAnalysisV2] Stage 2: Generating repository overview...")
        repo_overview = self._generate_repo_overview(repo_name, repo_description, parsed_files)

        # Stage 3: Explain each code unit with LLM (batched)
        print(f"[CodeAnalysisV2] Stage 3: Explaining code units (max {self.MAX_UNITS_TO_EXPLAIN})...")
        explained_units = self._explain_code_units(repo_name, repo_overview, parsed_files)
        print(f"[CodeAnalysisV2] Explained {len(explained_units)} code units")

        # Stage 4: Generate Mermaid diagrams
        print(f"[CodeAnalysisV2] Stage 4: Generating diagrams...")
        diagrams = self._generate_diagrams(repo_name, parsed_files, repo_overview)
        print(f"[CodeAnalysisV2] Generated {len(diagrams)} diagrams")

        # Stage 4.5: Generate cross-file flow documents (key for search quality)
        print(f"[CodeAnalysisV2] Stage 4.5: Generating flow documents...")
        flows = self._generate_flow_documents(repo_name, repo_overview, explained_units)
        print(f"[CodeAnalysisV2] Generated {len(flows)} flow documents")

        # Stage 5: Build documentation
        print(f"[CodeAnalysisV2] Stage 5: Building documentation...")
        documentation = self._build_documentation(repo_name, repo_overview, explained_units, diagrams)

        # Build V1-compatible file_analyses from explained units
        file_analyses = self._build_file_analyses(explained_units, parsed_files)

        # Stats
        language_counts = {}
        total_lines = 0
        for f in code_files:
            lang = f.get('language', 'Unknown')
            language_counts[lang] = language_counts.get(lang, 0) + 1
            total_lines += f.get('lines', 0)

        result = {
            'repository_overview': repo_overview,
            'file_analyses': file_analyses,
            'documentation': documentation,
            'code_units': explained_units,
            'diagrams': diagrams,
            'flows': flows,
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'stats': {
                'total_files': len(code_files),
                'analyzed_files': len(parsed_files),
                'total_units': total_units,
                'explained_units': len(explained_units),
                'total_lines': total_lines,
                'languages': language_counts,
                'diagrams_generated': len(diagrams),
                'flows_generated': len(flows),
            }
        }

        print(f"[CodeAnalysisV2] Analysis complete!")
        print(f"[CodeAnalysisV2]   Files: {len(code_files)}, Units: {total_units}, Explained: {len(explained_units)}, Diagrams: {len(diagrams)}")

        return result

    # =========================================================================
    # STAGE 2: REPOSITORY OVERVIEW
    # =========================================================================

    def _generate_repo_overview(self, repo_name: str, repo_description: Optional[str],
                                parsed_files: List[ParsedFile]) -> Dict:
        """Generate high-level overview from parsed structure (1 LLM call)"""

        # Build structural summary
        file_summary_lines = []
        for pf in parsed_files[:200]:
            classes = ', '.join(c.name for c in pf.classes) if pf.classes else ''
            functions = ', '.join(f.name for f in pf.functions[:5]) if pf.functions else ''
            parts = []
            if classes:
                parts.append(f"classes: {classes}")
            if functions:
                parts.append(f"functions: {functions}")
            if pf.imports:
                parts.append(f"{len(pf.imports)} imports")
            detail = f" ({'; '.join(parts)})" if parts else ''
            file_summary_lines.append(f"  {pf.file_path} [{pf.language}]{detail}")

        file_tree = '\n'.join(file_summary_lines)

        prompt = f"""Analyze this repository structure and provide a JSON overview.

Repository: {repo_name}
Description: {repo_description or 'N/A'}

Parsed Structure ({len(parsed_files)} files):
{file_tree}

Return ONLY a JSON object with:
- "architecture": 2-3 sentence architecture description
- "tech_stack": list of technologies
- "patterns": list of design patterns
- "components": dict mapping component names to directories
- "purpose": 1-2 sentence purpose description"""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a senior software architect. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            content = response.choices[0].message.content.strip()
            content = self._clean_json(content)
            return json.loads(content)
        except Exception as e:
            print(f"[CodeAnalysisV2] Overview generation failed: {e}")
            return {
                'architecture': f'Repository with {len(parsed_files)} files',
                'tech_stack': list(set(pf.language for pf in parsed_files if pf.language)),
                'patterns': [],
                'components': {},
                'purpose': repo_description or 'N/A'
            }

    # =========================================================================
    # STAGE 3: EXPLAIN CODE UNITS
    # =========================================================================

    def _explain_code_units(self, repo_name: str, repo_overview: Dict,
                            parsed_files: List[ParsedFile]) -> List[Dict]:
        """
        Generate natural language explanations for each code unit.
        Batches multiple units per LLM call for efficiency.
        """
        # Collect all units to explain
        all_units: List[Tuple[CodeUnit, ParsedFile]] = []
        for pf in parsed_files:
            for unit in pf.all_units:
                if unit.unit_type != 'import':
                    all_units.append((unit, pf))

        # Budget control
        if len(all_units) > self.MAX_UNITS_TO_EXPLAIN:
            print(f"[CodeAnalysisV2] Trimming {len(all_units)} units to {self.MAX_UNITS_TO_EXPLAIN}")
            # Prioritize: classes > functions > methods > modules
            priority = {'class': 0, 'function': 1, 'method': 2, 'export': 3, 'module': 4}
            all_units.sort(key=lambda x: (priority.get(x[0].unit_type, 5), -x[0].line_count))
            all_units = all_units[:self.MAX_UNITS_TO_EXPLAIN]

        explained = []

        # Process in batches
        for i in range(0, len(all_units), self.BATCH_SIZE):
            batch = all_units[i:i + self.BATCH_SIZE]
            batch_num = i // self.BATCH_SIZE + 1
            total_batches = (len(all_units) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            if batch_num % 10 == 1 or batch_num == total_batches:
                print(f"[CodeAnalysisV2]   Batch {batch_num}/{total_batches} ({len(batch)} units)")

            batch_explanations = self._explain_batch(batch, repo_name, repo_overview)
            explained.extend(batch_explanations)

        return explained

    def _explain_batch(self, batch: List[Tuple[CodeUnit, ParsedFile]],
                       repo_name: str, repo_overview: Dict) -> List[Dict]:
        """Explain a batch of code units in a single LLM call"""

        units_text = []
        for idx, (unit, pf) in enumerate(batch):
            code = unit.code[:self.MAX_CODE_PER_UNIT]
            units_text.append(f"""--- UNIT {idx + 1} ---
File: {pf.file_path}
Type: {unit.unit_type}
Name: {unit.qualified_name}
Lines: {unit.line_start}-{unit.line_end}
Code:
```
{code}
```""")

        all_units_text = '\n\n'.join(units_text)

        prompt = f"""You are documenting the {repo_name} codebase ({repo_overview.get('purpose', 'a software project')}).

For each code unit below, write a 3-5 sentence explanation as if answering the question "What does this do and how does it work?" for a new developer joining the team. Your explanation will be embedded in a search engine, so write it in a way that matches how developers ask questions.

Include:
1. What it does — in plain language someone would actually search for (e.g., "handles user login", "sends SMS notifications")
2. The step-by-step flow — what happens when this function/class is called, in order
3. Cross-references — which other functions/files/services this calls or is called by (use exact names)
4. Important details — error handling, side effects, external APIs called, business rules

{all_units_text}

Return a JSON array with one object per unit:
[
  {{
    "unit_index": 1,
    "explanation": "The authenticate() function handles user login by validating a JWT token from the Authorization header. It decodes the token using JWTUtils.decode(), looks up the user in the database via UserService.get_by_id(), and attaches the user to the request context. If the token is expired or invalid, it returns a 401 error. Called by all protected route handlers as middleware.",
    "key_details": ["validates JWT tokens", "calls UserService.get_by_id()", "called by route middleware", "returns 401 on invalid token"]
  }},
  ...
]

Return ONLY the JSON array. Be specific — mention actual function names, file names, and services."""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a senior developer writing precise code documentation. Return valid JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=self.MAX_EXPLANATION_TOKENS * len(batch)
            )
            content = response.choices[0].message.content.strip()
            content = self._clean_json(content)
            explanations_raw = json.loads(content)

            results = []
            for idx, (unit, pf) in enumerate(batch):
                # Match explanation to unit
                expl = None
                for e in explanations_raw:
                    if e.get('unit_index') == idx + 1:
                        expl = e
                        break

                if not expl and idx < len(explanations_raw):
                    expl = explanations_raw[idx]

                explanation = expl.get('explanation', f'{unit.unit_type} {unit.qualified_name}') if expl else f'{unit.unit_type} {unit.qualified_name}'
                key_details = expl.get('key_details', []) if expl else []

                results.append({
                    'file_path': pf.file_path,
                    'unit_type': unit.unit_type,
                    'name': unit.qualified_name,
                    'line_start': unit.line_start,
                    'line_end': unit.line_end,
                    'language': unit.language,
                    'code': unit.code[:self.MAX_CODE_PER_UNIT],
                    'explanation': explanation,
                    'key_details': key_details,
                    'docstring': unit.docstring,
                    'parent_class': unit.parent_class,
                })

            return results

        except Exception as e:
            print(f"[CodeAnalysisV2] Batch explanation failed: {e}")
            # Return basic info without LLM explanation
            results = []
            for unit, pf in batch:
                results.append({
                    'file_path': pf.file_path,
                    'unit_type': unit.unit_type,
                    'name': unit.qualified_name,
                    'line_start': unit.line_start,
                    'line_end': unit.line_end,
                    'language': unit.language,
                    'code': unit.code[:self.MAX_CODE_PER_UNIT],
                    'explanation': unit.docstring or f'{unit.unit_type} {unit.qualified_name} in {pf.file_path}',
                    'key_details': [],
                    'docstring': unit.docstring,
                    'parent_class': unit.parent_class,
                })
            return results

    # =========================================================================
    # STAGE 4.5: FLOW DOCUMENT GENERATION
    # =========================================================================

    def _generate_flow_documents(self, repo_name: str, repo_overview: Dict,
                                 explained_units: List[Dict]) -> List[Dict]:
        """
        Generate cross-file flow documents that trace how data/requests move through the system.
        These match conversational queries like "what happens when X" much better than individual function docs.
        """
        if len(explained_units) < 5:
            return []

        # Build a summary of all explained units for the LLM
        unit_summaries = []
        for u in explained_units[:200]:  # Cap to avoid token overflow
            unit_summaries.append(
                f"- {u['name']} ({u['unit_type']}) in {u['file_path']}: {u['explanation'][:200]}"
            )
        units_text = '\n'.join(unit_summaries)

        prompt = f"""You are documenting the {repo_name} codebase ({repo_overview.get('purpose', 'a software project')}).

Below is a list of all the functions/classes in this codebase with brief descriptions. Your job is to identify the 3-5 most important end-to-end flows and write a detailed walkthrough of each.

A "flow" traces what happens from a user action or external trigger through the entire system. Examples: "User submits a form → validation → API call → database save → response", "Cron job triggers → data processing → notification sent".

CODE UNITS:
{units_text}

For each flow, write:
1. A clear title phrased as a question someone would ask (e.g., "What happens when a patient texts YES to a ride offer?")
2. A step-by-step walkthrough naming the exact functions, files, and services involved at each step
3. Key technical details at each step (what data is passed, what decisions are made, what external services are called)

Return a JSON array:
[
  {{
    "title": "What happens when a patient texts YES to a ride offer?",
    "description": "End-to-end flow from incoming SMS to ride booking",
    "steps": [
      "1. Twilio webhook hits POST /api/sms/webhook in sms.routes.ts",
      "2. createSMSRoutes() handler calls ClaudeService.parseIntent() to understand the message",
      "3. If intent is CONFIRM_RIDE, it calls RideService.bookRide() with patient and appointment details",
      "..."
    ],
    "files_involved": ["sms.routes.ts", "claude.service.ts", "rides.routes.ts"],
    "key_concepts": ["Natural language intent parsing", "Automated ride booking", "SMS webhook handling"]
  }}
]

Return ONLY valid JSON. Identify the most important flows that a new developer would ask about."""

        try:
            response = self.client.chat.completions.create(
                model=AZURE_CHAT_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": "You are a senior developer writing cross-functional flow documentation. Return valid JSON arrays only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )
            content = response.choices[0].message.content.strip()
            content = self._clean_json(content)
            flows = json.loads(content)

            if not isinstance(flows, list):
                return []

            return flows[:5]  # Cap at 5 flows

        except Exception as e:
            print(f"[CodeAnalysisV2] Flow document generation failed: {e}")
            return []

    # =========================================================================
    # STAGE 4: DIAGRAM GENERATION
    # =========================================================================

    def _generate_diagrams(self, repo_name: str, parsed_files: List[ParsedFile],
                           repo_overview: Dict) -> List[Dict]:
        """Generate Mermaid diagrams from parsed code structure"""
        diagrams = []

        # 1. Architecture diagram (module-to-module)
        arch_diagram = self._generate_architecture_diagram(repo_name, parsed_files, repo_overview)
        if arch_diagram:
            diagrams.append(arch_diagram)

        # 2. Class hierarchy diagram
        class_diagram = self._generate_class_diagram(repo_name, parsed_files)
        if class_diagram:
            diagrams.append(class_diagram)

        # 3. Call flow diagrams for key entry points
        call_diagrams = self._generate_call_flow_diagrams(repo_name, parsed_files)
        diagrams.extend(call_diagrams)

        return diagrams

    def _generate_architecture_diagram(self, repo_name: str, parsed_files: List[ParsedFile],
                                       repo_overview: Dict) -> Optional[Dict]:
        """Generate high-level architecture Mermaid diagram"""
        # Group files by top-level directory
        dir_contents: Dict[str, List[str]] = {}
        for pf in parsed_files:
            parts = pf.file_path.split('/')
            top_dir = parts[0] if len(parts) > 1 else 'root'
            if top_dir not in dir_contents:
                dir_contents[top_dir] = []
            classes = [c.name for c in pf.classes]
            functions = [f.name for f in pf.functions[:3]]
            items = classes + functions
            if items:
                dir_contents[top_dir].extend(items[:3])

        if len(dir_contents) < 2:
            return None

        # Build import graph for edges
        import_graph = self.parser.extract_import_graph(parsed_files)
        dir_edges: set = set()
        for src, targets in import_graph.items():
            src_dir = src.split('/')[0] if '/' in src else 'root'
            for tgt in targets:
                tgt_dir = tgt.split('/')[0] if '/' in tgt else 'root'
                if src_dir != tgt_dir:
                    dir_edges.add((src_dir, tgt_dir))

        # Generate Mermaid
        lines = ['graph TD']
        for d, items in dir_contents.items():
            safe_d = d.replace('-', '_').replace('.', '_')
            item_list = ', '.join(items[:3])
            lines.append(f'    {safe_d}["{d}<br/><small>{item_list}</small>"]')

        for src, tgt in dir_edges:
            safe_src = src.replace('-', '_').replace('.', '_')
            safe_tgt = tgt.replace('-', '_').replace('.', '_')
            lines.append(f'    {safe_src} --> {safe_tgt}')

        # If no edges from imports, create edges from common patterns
        if not dir_edges and len(dir_contents) > 1:
            dirs = list(dir_contents.keys())
            for i in range(min(len(dirs) - 1, 5)):
                safe_src = dirs[i].replace('-', '_').replace('.', '_')
                safe_tgt = dirs[i + 1].replace('-', '_').replace('.', '_')
                lines.append(f'    {safe_src} --- {safe_tgt}')

        mermaid = '\n'.join(lines)
        description = f"Architecture diagram for {repo_name} showing {len(dir_contents)} main modules/directories and their relationships. "
        description += f"Modules: {', '.join(dir_contents.keys())}."

        return {
            'diagram_type': 'architecture',
            'title': f'{repo_name} - Architecture Overview',
            'mermaid': mermaid,
            'description': description,
        }

    def _generate_class_diagram(self, repo_name: str, parsed_files: List[ParsedFile]) -> Optional[Dict]:
        """Generate class hierarchy Mermaid diagram"""
        classes = []
        for pf in parsed_files:
            for cls in pf.classes:
                methods = [m.name for m in cls.children[:5]]
                classes.append({
                    'name': cls.name,
                    'file': pf.file_path,
                    'methods': methods,
                })

        if len(classes) < 2:
            return None

        # Limit to 15 most important classes
        classes = classes[:15]

        lines = ['classDiagram']
        for cls in classes:
            safe_name = cls['name'].replace('<', '').replace('>', '')
            lines.append(f'    class {safe_name} {{')
            for m in cls['methods'][:4]:
                lines.append(f'        +{m}()')
            lines.append(f'    }}')

        mermaid = '\n'.join(lines)
        class_names = [c['name'] for c in classes]
        description = f"Class diagram for {repo_name} showing {len(classes)} classes and their methods. "
        description += f"Classes: {', '.join(class_names)}."

        return {
            'diagram_type': 'class_hierarchy',
            'title': f'{repo_name} - Class Hierarchy',
            'mermaid': mermaid,
            'description': description,
        }

    def _generate_call_flow_diagrams(self, repo_name: str,
                                     parsed_files: List[ParsedFile]) -> List[Dict]:
        """Generate call flow diagrams for key entry points"""
        call_graph = self.parser.extract_call_relationships(parsed_files)

        if not call_graph:
            return []

        # Find entry points (functions called by many others, or with "main", "app", "handler" in name)
        call_counts: Dict[str, int] = {}
        for caller, callees in call_graph.items():
            for callee in callees:
                call_counts[callee] = call_counts.get(callee, 0) + 1

        # Pick top entry points
        entry_keywords = ('main', 'app', 'handler', 'route', 'api', 'endpoint', 'index', 'server')
        entry_points = []
        for func_path, count in sorted(call_counts.items(), key=lambda x: -x[1])[:10]:
            name = func_path.split(':')[-1].lower()
            is_entry = any(kw in name for kw in entry_keywords)
            if is_entry or count >= 2:
                entry_points.append(func_path)

        if not entry_points:
            return []

        diagrams = []
        for entry in entry_points[:3]:  # Max 3 flow diagrams
            lines = ['sequenceDiagram']
            entry_name = entry.split(':')[-1]

            # Build call chain (max depth 5)
            visited = set()
            chain = self._trace_calls(entry, call_graph, visited, max_depth=5)

            if len(chain) < 2:
                continue

            for caller_name, callee_name in chain:
                c1 = caller_name.split(':')[-1]
                c2 = callee_name.split(':')[-1]
                lines.append(f'    {c1}->>+{c2}: calls')
                lines.append(f'    {c2}-->>-{c1}: returns')

            if len(lines) <= 1:
                continue

            mermaid = '\n'.join(lines)
            description = f"Call flow starting from {entry_name}, showing the sequence of function calls. "
            called_funcs = [c[1].split(':')[-1] for c in chain]
            description += f"Flow: {entry_name} -> {' -> '.join(called_funcs)}."

            diagrams.append({
                'diagram_type': 'call_flow',
                'title': f'{repo_name} - {entry_name} Call Flow',
                'mermaid': mermaid,
                'description': description,
            })

        return diagrams

    def _trace_calls(self, func: str, call_graph: Dict[str, List[str]],
                     visited: set, max_depth: int) -> List[Tuple[str, str]]:
        """Trace call chain from a function"""
        if max_depth <= 0 or func in visited:
            return []

        visited.add(func)
        chain = []

        callees = call_graph.get(func, [])
        for callee in callees[:3]:  # Max 3 branches per level
            chain.append((func, callee))
            chain.extend(self._trace_calls(callee, call_graph, visited, max_depth - 1))

        return chain

    # =========================================================================
    # STAGE 5: BUILD DOCUMENTATION
    # =========================================================================

    def _build_documentation(self, repo_name: str, repo_overview: Dict,
                             explained_units: List[Dict], diagrams: List[Dict]) -> str:
        """Build comprehensive markdown documentation"""
        sections = []

        # Title
        sections.append(f"# {repo_name} - Technical Documentation\n")

        # Overview
        sections.append("## Overview\n")
        sections.append(f"{repo_overview.get('purpose', 'N/A')}\n")
        sections.append(f"\n**Architecture:** {repo_overview.get('architecture', 'N/A')}\n")

        # Tech stack
        tech = repo_overview.get('tech_stack', [])
        if tech:
            sections.append("\n## Technology Stack\n")
            for t in tech:
                sections.append(f"- {t}")
            sections.append("")

        # Diagrams
        if diagrams:
            sections.append("\n## Architecture Diagrams\n")
            for d in diagrams:
                sections.append(f"### {d['title']}\n")
                sections.append(f"{d['description']}\n")
                sections.append(f"```mermaid\n{d['mermaid']}\n```\n")

        # Code units by file
        sections.append("\n## Code Reference\n")
        units_by_file: Dict[str, List[Dict]] = {}
        for u in explained_units:
            fp = u['file_path']
            if fp not in units_by_file:
                units_by_file[fp] = []
            units_by_file[fp].append(u)

        for fp, units in sorted(units_by_file.items()):
            sections.append(f"\n### {fp}\n")
            for u in units:
                type_badge = u['unit_type'].upper()
                sections.append(f"**[{type_badge}] {u['name']}** (lines {u['line_start']}-{u['line_end']})")
                sections.append(f"\n{u['explanation']}\n")

        return '\n'.join(sections)

    # =========================================================================
    # V1 COMPATIBILITY: Build file_analyses from explained units
    # =========================================================================

    def _build_file_analyses(self, explained_units: List[Dict],
                             parsed_files: List[ParsedFile]) -> List[Dict]:
        """Build V1-compatible file analyses from explained units"""
        file_map: Dict[str, Dict] = {}

        for pf in parsed_files:
            file_map[pf.file_path] = {
                'file_path': pf.file_path,
                'language': pf.language,
                'lines': pf.content.count('\n') + 1,
                'summary': '',
                'key_functions': [],
                'dependencies': [i.name for i in pf.imports],
                'business_logic': '',
                'api_endpoints': [],
                'data_models': [],
                'important_notes': [],
            }

        # Fill in from explained units
        for u in explained_units:
            fp = u['file_path']
            if fp not in file_map:
                continue

            fa = file_map[fp]
            if u['unit_type'] in ('function', 'method'):
                fa['key_functions'].append(u['name'])
            elif u['unit_type'] == 'class':
                fa['data_models'].append(u['name'])

            # Build summary from first few explanations
            if not fa['summary']:
                fa['summary'] = u['explanation']
            elif len(fa['summary']) < 500:
                fa['summary'] += ' ' + u['explanation']

        return list(file_map.values())

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _clean_json(self, content: str) -> str:
        """Remove markdown code blocks from LLM response"""
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()
        return content
