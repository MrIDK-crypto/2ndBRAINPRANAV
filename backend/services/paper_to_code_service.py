"""
Paper-to-Code Service
Takes paper text and generates a Python implementation using GPT.
Streams SSE events for each pipeline step.
"""

import json
import re
import traceback
from typing import Generator

from services.openai_client import get_openai_client


class PaperToCodeService:
    """Extracts methods from research papers and generates Python implementations."""

    def __init__(self):
        self.openai = get_openai_client()

    # ── Public entry point ────────────────────────────────────────────────

    def generate(
        self,
        paper_text: str,
        field: str = '',
        paper_type: str = 'experimental',
        focus_section: str = '',
    ) -> Generator[str, None, None]:
        """
        Main pipeline. Yields SSE event strings for each step:
          1. Extract method
          2. Generate structure
          3. Generate code
          4. Generate tests
          5. Generate meta (README + requirements)
        """
        all_files: list[dict] = []

        try:
            # ── Step 1: Extract method ────────────────────────────────────
            yield self._sse('progress', {'step': 1, 'message': 'Extracting core method from paper...', 'percent': 10})
            method_info = self._extract_method(paper_text, field, paper_type, focus_section)
            yield self._sse('method_extracted', method_info)

            # ── Step 2: Generate project structure ────────────────────────
            yield self._sse('progress', {'step': 2, 'message': 'Designing project structure...', 'percent': 25})
            structure = self._generate_structure(method_info)
            yield self._sse('structure', structure)

            # ── Step 3: Generate code ─────────────────────────────────────
            yield self._sse('progress', {'step': 3, 'message': 'Generating implementation code...', 'percent': 40})
            code_files = self._generate_code(method_info, structure, paper_text)
            all_files.extend(code_files)
            yield self._sse('code_generated', {'files': code_files})

            # ── Step 4: Generate tests ────────────────────────────────────
            yield self._sse('progress', {'step': 4, 'message': 'Generating test suite...', 'percent': 65})
            test_files = self._generate_tests(method_info, code_files)
            all_files.extend(test_files)
            yield self._sse('tests_generated', {'files': test_files})

            # ── Step 5: Generate meta files ───────────────────────────────
            yield self._sse('progress', {'step': 5, 'message': 'Generating README and requirements...', 'percent': 85})
            meta_files = self._generate_meta(method_info, code_files)
            all_files.extend(meta_files)
            yield self._sse('meta_generated', {'files': meta_files})

            # ── Done ──────────────────────────────────────────────────────
            yield self._sse('progress', {'step': 5, 'message': 'Complete!', 'percent': 100})
            yield self._sse('complete', {
                'files': all_files,
                'method': method_info,
                'structure': structure,
            })

        except Exception as e:
            print(f"[PaperToCode] Pipeline error: {e}", flush=True)
            traceback.print_exc()
            yield self._sse('error', {'error': str(e)})

    # ── SSE helper ────────────────────────────────────────────────────────

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    # ── Step 1: Extract method ────────────────────────────────────────────

    def _extract_method(self, paper_text: str, field: str, paper_type: str, focus_section: str) -> dict:
        text_excerpt = paper_text[:12000]

        focus_instruction = ''
        if focus_section:
            focus_instruction = f"\nFocus especially on the section: {focus_section}\n"

        prompt = (
            "You are an expert research scientist. Analyze the following research paper excerpt and "
            "extract the CORE algorithm, method, or model described.\n\n"
            f"Field: {field or 'auto-detect'}\n"
            f"Paper type: {paper_type}\n"
            f"{focus_instruction}\n"
            "Return a JSON object with these keys:\n"
            "- method_name: string — concise name of the method (e.g. 'Graph Attention Network')\n"
            "- summary: string — 2-3 sentence description of what the method does\n"
            "- inputs: list of strings — what the method takes as input\n"
            "- outputs: list of strings — what the method produces\n"
            "- steps: list of strings — ordered algorithmic steps\n"
            "- dependencies: list of strings — Python packages needed (e.g. 'numpy', 'torch')\n"
            "- hyperparameters: list of objects with keys 'name', 'default', 'description'\n\n"
            "Return ONLY the JSON object, no markdown fences.\n\n"
            f"PAPER EXCERPT:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        return {
            "method_name": "ExtractedMethod",
            "summary": "Method extracted from paper.",
            "inputs": ["data"],
            "outputs": ["result"],
            "steps": ["Process input data", "Return result"],
            "dependencies": ["numpy"],
            "hyperparameters": [],
        }

    # ── Step 2: Generate structure ────────────────────────────────────────

    def _generate_structure(self, method_info: dict) -> dict:
        safe_name = re.sub(r'[^a-z0-9]+', '_', method_info.get('method_name', 'method').lower()).strip('_')
        project_name = safe_name or 'method_impl'

        structure = {
            "project_name": project_name,
            "directories": [
                project_name,
                f"{project_name}/tests",
            ],
            "files": [
                f"{project_name}/__init__.py",
                f"{project_name}/model.py",
                f"{project_name}/utils.py",
                f"{project_name}/config.py",
                f"{project_name}/run_example.py",
                f"{project_name}/tests/__init__.py",
                f"{project_name}/tests/test_model.py",
                f"{project_name}/tests/test_utils.py",
                f"{project_name}/README.md",
                f"{project_name}/requirements.txt",
            ],
        }
        return structure

    # ── Step 3: Generate code ─────────────────────────────────────────────

    def _generate_code(self, method_info: dict, structure: dict, paper_text: str) -> list[dict]:
        project = structure['project_name']
        text_excerpt = paper_text[:8000]

        deps_str = ', '.join(method_info.get('dependencies', ['numpy']))
        steps_str = '\n'.join(f"  {i+1}. {s}" for i, s in enumerate(method_info.get('steps', [])))
        hp_str = '\n'.join(
            f"  - {h.get('name', '?')}: {h.get('default', 'N/A')} — {h.get('description', '')}"
            for h in method_info.get('hyperparameters', [])
        )

        prompt = (
            "You are an expert Python developer implementing a research paper's method.\n\n"
            f"Method: {method_info.get('method_name', 'Method')}\n"
            f"Summary: {method_info.get('summary', '')}\n"
            f"Inputs: {method_info.get('inputs', [])}\n"
            f"Outputs: {method_info.get('outputs', [])}\n"
            f"Steps:\n{steps_str}\n"
            f"Hyperparameters:\n{hp_str}\n"
            f"Dependencies: {deps_str}\n\n"
            "Generate 4 Python files. Return a JSON array of objects, each with 'path' and 'content' keys.\n\n"
            "Files to generate:\n"
            f"1. '{project}/model.py' — Main implementation of the method as a class or function(s). "
            "Include docstrings, type hints, and match the paper's algorithm closely.\n"
            f"2. '{project}/utils.py' — Helper functions (data loading, preprocessing, visualization).\n"
            f"3. '{project}/config.py' — Configuration dataclass with all hyperparameters and defaults.\n"
            f"4. '{project}/run_example.py' — Runnable example that demonstrates the method with synthetic data.\n\n"
            "Requirements:\n"
            "- Use modern Python (3.10+) with type hints\n"
            "- Add comprehensive docstrings\n"
            "- Make the code actually runnable\n"
            "- Use the paper's notation in comments where helpful\n"
            "- Include proper __init__.py with public API exports\n\n"
            "Return ONLY the JSON array, no markdown fences.\n\n"
            f"Paper excerpt for reference:\n{text_excerpt}"
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=8000,
        )
        raw = resp.choices[0].message.content.strip()

        files = self._parse_file_array(raw)
        if not files:
            files = [
                {"path": f"{project}/model.py", "content": f'"""Main implementation of {method_info.get("method_name", "Method")}."""\n\nclass Model:\n    pass\n'},
                {"path": f"{project}/utils.py", "content": '"""Utility functions."""\n'},
                {"path": f"{project}/config.py", "content": '"""Configuration."""\n\nfrom dataclasses import dataclass\n\n@dataclass\nclass Config:\n    pass\n'},
                {"path": f"{project}/run_example.py", "content": '"""Example usage."""\n\ndef main():\n    print("Run example")\n\nif __name__ == "__main__":\n    main()\n'},
            ]

        # Add __init__.py
        files.insert(0, {
            "path": f"{project}/__init__.py",
            "content": f'"""{method_info.get("method_name", "Method")} — Implementation from paper."""\n',
        })

        return files

    # ── Step 4: Generate tests ────────────────────────────────────────────

    def _generate_tests(self, method_info: dict, code_files: list[dict]) -> list[dict]:
        # Build a summary of the generated code for context
        code_summary = ""
        for f in code_files:
            code_summary += f"\n--- {f['path']} ---\n{f['content'][:2000]}\n"

        project = code_files[0]['path'].split('/')[0] if code_files else 'method_impl'

        prompt = (
            "You are an expert Python test engineer. Generate pytest test files for the following implementation.\n\n"
            f"Method: {method_info.get('method_name', 'Method')}\n"
            f"Summary: {method_info.get('summary', '')}\n\n"
            f"Code to test:\n{code_summary}\n\n"
            "Generate 2 test files as a JSON array of objects with 'path' and 'content' keys:\n"
            f"1. '{project}/tests/test_model.py' — Tests for the main model/algorithm\n"
            f"2. '{project}/tests/test_utils.py' — Tests for utility functions\n\n"
            "Requirements:\n"
            "- Use pytest (not unittest)\n"
            "- Include at least 3 tests per file\n"
            "- Test edge cases and expected outputs\n"
            "- Use parametrize where appropriate\n"
            "- Add descriptive test names\n\n"
            "Return ONLY the JSON array, no markdown fences."
        )

        resp = self.openai.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4000,
        )
        raw = resp.choices[0].message.content.strip()

        files = self._parse_file_array(raw)
        if not files:
            files = [
                {"path": f"{project}/tests/test_model.py", "content": f'"""Tests for {method_info.get("method_name", "Model")}."""\nimport pytest\n\ndef test_placeholder():\n    assert True\n'},
                {"path": f"{project}/tests/test_utils.py", "content": '"""Tests for utilities."""\nimport pytest\n\ndef test_placeholder():\n    assert True\n'},
            ]

        # Add tests __init__.py
        files.insert(0, {
            "path": f"{project}/tests/__init__.py",
            "content": "",
        })

        return files

    # ── Step 5: Generate meta ─────────────────────────────────────────────

    def _generate_meta(self, method_info: dict, code_files: list[dict]) -> list[dict]:
        project = code_files[0]['path'].split('/')[0] if code_files else 'method_impl'
        deps = method_info.get('dependencies', ['numpy'])
        method_name = method_info.get('method_name', 'Method')
        summary = method_info.get('summary', '')
        steps = method_info.get('steps', [])
        inputs = method_info.get('inputs', [])
        outputs = method_info.get('outputs', [])

        # Build README
        steps_md = '\n'.join(f"{i+1}. {s}" for i, s in enumerate(steps))
        inputs_md = '\n'.join(f"- {inp}" for inp in inputs)
        outputs_md = '\n'.join(f"- {out}" for out in outputs)
        hp_md = '\n'.join(
            f"| `{h.get('name', '')}` | `{h.get('default', '')}` | {h.get('description', '')} |"
            for h in method_info.get('hyperparameters', [])
        )

        readme = (
            f"# {method_name}\n\n"
            f"{summary}\n\n"
            "## Installation\n\n"
            "```bash\n"
            "pip install -r requirements.txt\n"
            "```\n\n"
            "## Usage\n\n"
            "```bash\n"
            f"python -m {project}.run_example\n"
            "```\n\n"
            "## Method Overview\n\n"
            f"### Inputs\n{inputs_md}\n\n"
            f"### Outputs\n{outputs_md}\n\n"
            f"### Steps\n{steps_md}\n\n"
        )
        if hp_md:
            readme += (
                "### Hyperparameters\n\n"
                "| Name | Default | Description |\n"
                "|------|---------|-------------|\n"
                f"{hp_md}\n\n"
            )
        readme += (
            "## Tests\n\n"
            "```bash\n"
            "pytest\n"
            "```\n\n"
            "---\n"
            "*Generated by 2nd Brain Paper-to-Code*\n"
        )

        # Build requirements.txt
        base_deps = ['pytest>=7.0']
        for d in deps:
            if d.lower() not in ('pytest',):
                base_deps.append(d)
        requirements = '\n'.join(sorted(set(base_deps))) + '\n'

        return [
            {"path": f"{project}/README.md", "content": readme},
            {"path": f"{project}/requirements.txt", "content": requirements},
        ]

    # ── JSON parsing helper ───────────────────────────────────────────────

    @staticmethod
    def _parse_file_array(raw: str) -> list[dict]:
        """Parse a JSON array of {path, content} from GPT output."""
        # Try direct parse
        try:
            result = json.loads(raw)
            if isinstance(result, list):
                return [f for f in result if isinstance(f, dict) and 'path' in f and 'content' in f]
        except json.JSONDecodeError:
            pass

        # Try extracting array from markdown fences or surrounding text
        arr_match = re.search(r'\[.*\]', raw, re.DOTALL)
        if arr_match:
            try:
                result = json.loads(arr_match.group())
                if isinstance(result, list):
                    return [f for f in result if isinstance(f, dict) and 'path' in f and 'content' in f]
            except json.JSONDecodeError:
                pass

        return []


# ── Singleton ─────────────────────────────────────────────────────────────

_service = None


def get_paper_to_code_service() -> PaperToCodeService:
    global _service
    if _service is None:
        _service = PaperToCodeService()
    return _service
