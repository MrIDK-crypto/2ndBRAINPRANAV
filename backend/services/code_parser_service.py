"""
Code Parser Service - Tree-sitter based structural code analysis

Parses source code into structured units (functions, classes, imports)
using tree-sitter ASTs. This replaces character-based chunking with
semantic, structure-aware parsing.

Supports: Python, JavaScript, TypeScript, Java, Go, Ruby, PHP, C, C++,
Rust, Kotlin, Swift, Scala, CSS, HTML, YAML, JSON, Bash, SQL, C#
"""

import os
import re
from typing import Dict, List, Optional, Tuple

# tree-sitter imports
try:
    import tree_sitter_languages
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("[CodeParser] tree-sitter-languages not installed. Run: pip install tree-sitter-languages")


# Mapping from file extensions to tree-sitter language names
EXT_TO_LANGUAGE = {
    '.py': 'python',
    '.js': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rb': 'ruby',
    '.php': 'php',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.hpp': 'cpp',
    '.cc': 'cpp',
    '.rs': 'rust',
    '.kt': 'kotlin',
    '.swift': 'swift',
    '.scala': 'scala',
    '.cs': 'c_sharp',
    '.css': 'css',
    '.html': 'html',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.sh': 'bash',
    '.bash': 'bash',
    '.sql': 'sql',
    '.lua': 'lua',
    '.r': 'r',
    '.R': 'r',
}

# Tree-sitter node types that represent "definitions" per language
DEFINITION_TYPES = {
    'python': {
        'function': ['function_definition'],
        'class': ['class_definition'],
        'import': ['import_statement', 'import_from_statement'],
    },
    'javascript': {
        'function': ['function_declaration', 'arrow_function', 'method_definition', 'function'],
        'class': ['class_declaration'],
        'import': ['import_statement'],
        'export': ['export_statement'],
    },
    'typescript': {
        'function': ['function_declaration', 'arrow_function', 'method_definition', 'function'],
        'class': ['class_declaration'],
        'import': ['import_statement'],
        'export': ['export_statement'],
        'interface': ['interface_declaration'],
        'type_alias': ['type_alias_declaration'],
    },
    'java': {
        'function': ['method_declaration', 'constructor_declaration'],
        'class': ['class_declaration', 'interface_declaration', 'enum_declaration'],
        'import': ['import_declaration'],
    },
    'go': {
        'function': ['function_declaration', 'method_declaration'],
        'class': ['type_declaration'],  # Go structs
        'import': ['import_declaration'],
    },
    'ruby': {
        'function': ['method', 'singleton_method'],
        'class': ['class', 'module'],
        'import': ['call'],  # require/include
    },
    'php': {
        'function': ['function_definition', 'method_declaration'],
        'class': ['class_declaration', 'interface_declaration', 'trait_declaration'],
        'import': ['namespace_use_declaration'],
    },
    'c': {
        'function': ['function_definition'],
        'class': ['struct_specifier', 'enum_specifier', 'union_specifier'],
        'import': ['preproc_include'],
    },
    'cpp': {
        'function': ['function_definition'],
        'class': ['class_specifier', 'struct_specifier', 'enum_specifier'],
        'import': ['preproc_include', 'using_declaration'],
    },
    'rust': {
        'function': ['function_item'],
        'class': ['struct_item', 'enum_item', 'impl_item', 'trait_item'],
        'import': ['use_declaration'],
    },
    'kotlin': {
        'function': ['function_declaration'],
        'class': ['class_declaration', 'object_declaration', 'interface_declaration'],
        'import': ['import_header'],
    },
    'swift': {
        'function': ['function_declaration'],
        'class': ['class_declaration', 'struct_declaration', 'protocol_declaration', 'enum_declaration'],
        'import': ['import_declaration'],
    },
    'scala': {
        'function': ['function_definition'],
        'class': ['class_definition', 'object_definition', 'trait_definition'],
        'import': ['import_declaration'],
    },
    'c_sharp': {
        'function': ['method_declaration', 'constructor_declaration'],
        'class': ['class_declaration', 'interface_declaration', 'struct_declaration', 'enum_declaration'],
        'import': ['using_directive'],
    },
}


class CodeUnit:
    """Represents a parsed code unit (function, class, import, etc.)"""

    def __init__(
        self,
        unit_type: str,       # 'function', 'class', 'import', 'module'
        name: str,
        code: str,
        line_start: int,
        line_end: int,
        file_path: str,
        language: str,
        parent_class: Optional[str] = None,
        docstring: Optional[str] = None,
        children: Optional[List['CodeUnit']] = None,
    ):
        self.unit_type = unit_type
        self.name = name
        self.code = code
        self.line_start = line_start
        self.line_end = line_end
        self.file_path = file_path
        self.language = language
        self.parent_class = parent_class
        self.docstring = docstring
        self.children = children or []

    def to_dict(self) -> Dict:
        return {
            'unit_type': self.unit_type,
            'name': self.name,
            'code': self.code,
            'line_start': self.line_start,
            'line_end': self.line_end,
            'file_path': self.file_path,
            'language': self.language,
            'parent_class': self.parent_class,
            'docstring': self.docstring,
            'children': [c.to_dict() for c in self.children],
        }

    @property
    def qualified_name(self) -> str:
        if self.parent_class:
            return f"{self.parent_class}.{self.name}"
        return self.name

    @property
    def line_count(self) -> int:
        return self.line_end - self.line_start + 1


class ParsedFile:
    """Represents a fully parsed source file"""

    def __init__(self, file_path: str, language: str, content: str):
        self.file_path = file_path
        self.language = language
        self.content = content
        self.functions: List[CodeUnit] = []
        self.classes: List[CodeUnit] = []
        self.imports: List[CodeUnit] = []
        self.module_doc: Optional[str] = None
        self.parse_success: bool = False
        self.parse_error: Optional[str] = None

    @property
    def all_units(self) -> List[CodeUnit]:
        """All code units in this file (functions + classes + their methods)"""
        units = []
        units.extend(self.functions)
        for cls in self.classes:
            units.append(cls)
            units.extend(cls.children)
        return units

    @property
    def total_units(self) -> int:
        count = len(self.functions)
        for cls in self.classes:
            count += 1 + len(cls.children)
        return count

    def to_dict(self) -> Dict:
        return {
            'file_path': self.file_path,
            'language': self.language,
            'parse_success': self.parse_success,
            'module_doc': self.module_doc,
            'functions': [f.to_dict() for f in self.functions],
            'classes': [c.to_dict() for c in self.classes],
            'imports': [i.to_dict() for i in self.imports],
            'total_units': self.total_units,
        }


class CodeParserService:
    """
    Parse source code files using tree-sitter to extract structured code units.

    This replaces the old approach of sending raw file text to the LLM.
    Instead, we parse into functions, classes, and imports — each becoming
    its own searchable, embeddable unit.
    """

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            print("[CodeParser] WARNING: tree-sitter-languages not available. Falling back to regex parsing.")

    def parse_file(self, file_path: str, content: str, language_hint: str = None) -> ParsedFile:
        """
        Parse a single file into structured code units.

        Args:
            file_path: Path to file (for extension detection)
            content: File content as string
            language_hint: Optional language hint (e.g. 'Python')

        Returns:
            ParsedFile with extracted functions, classes, imports
        """
        # Determine tree-sitter language
        _, ext = os.path.splitext(file_path)
        ts_lang = EXT_TO_LANGUAGE.get(ext.lower())

        parsed = ParsedFile(file_path=file_path, language=ts_lang or ext.lstrip('.'), content=content)

        if not content or not content.strip():
            parsed.parse_success = True
            return parsed

        # Try tree-sitter first
        if TREE_SITTER_AVAILABLE and ts_lang:
            try:
                self._parse_with_tree_sitter(parsed, content, ts_lang)
                parsed.parse_success = True
                return parsed
            except Exception as e:
                parsed.parse_error = str(e)
                print(f"[CodeParser] tree-sitter failed for {file_path}: {e}")

        # Fallback: regex-based parsing for common languages
        try:
            self._parse_with_regex(parsed, content, ext.lower())
            parsed.parse_success = True
        except Exception as e:
            parsed.parse_error = str(e)
            # Last resort: treat entire file as one unit
            parsed.functions.append(CodeUnit(
                unit_type='module',
                name=os.path.basename(file_path),
                code=content[:50000],  # Safety cap
                line_start=1,
                line_end=content.count('\n') + 1,
                file_path=file_path,
                language=parsed.language,
            ))
            parsed.parse_success = True

        return parsed

    def parse_files(self, code_files: List[Dict]) -> List[ParsedFile]:
        """
        Parse multiple code files.

        Args:
            code_files: List of dicts with 'path', 'content', 'language'

        Returns:
            List of ParsedFile objects
        """
        results = []
        for f in code_files:
            parsed = self.parse_file(
                file_path=f.get('path', ''),
                content=f.get('content', ''),
                language_hint=f.get('language'),
            )
            results.append(parsed)
        return results

    # =========================================================================
    # TREE-SITTER PARSING
    # =========================================================================

    def _parse_with_tree_sitter(self, parsed: ParsedFile, content: str, ts_lang: str):
        """Parse using tree-sitter AST"""
        parser = tree_sitter_languages.get_parser(ts_lang)
        tree = parser.parse(content.encode('utf-8'))
        root = tree.root_node

        # Get language-specific definition types
        lang_defs = DEFINITION_TYPES.get(ts_lang, {})
        func_types = set(lang_defs.get('function', []))
        class_types = set(lang_defs.get('class', []))
        import_types = set(lang_defs.get('import', []))

        # Extract module-level docstring
        parsed.module_doc = self._extract_module_docstring(root, ts_lang, content)

        # Walk the AST at top level
        for child in root.children:
            node_type = child.type

            if node_type in import_types:
                self._extract_import(parsed, child, content, ts_lang)

            elif node_type in class_types:
                self._extract_class(parsed, child, content, ts_lang, func_types)

            elif node_type in func_types:
                self._extract_function(parsed, child, content, ts_lang)

            elif node_type == 'decorated_definition' and ts_lang == 'python':
                # Python decorated functions/classes — use the inner def/class node for name
                for sub in child.children:
                    if sub.type in func_types:
                        name = self._get_node_name(sub, ts_lang)
                        code = content[child.start_byte:child.end_byte]
                        docstring = self._extract_docstring(sub, ts_lang, content)
                        unit = CodeUnit(
                            unit_type='function', name=name, code=code,
                            line_start=child.start_point[0] + 1,
                            line_end=child.end_point[0] + 1,
                            file_path=parsed.file_path, language=ts_lang,
                            docstring=docstring,
                        )
                        parsed.functions.append(unit)
                        break
                    elif sub.type in class_types:
                        self._extract_class(parsed, child, content, ts_lang, func_types)
                        break

            elif node_type == 'expression_statement' and ts_lang in ('javascript', 'typescript'):
                # Handle module.exports, const X = () => {}, etc.
                self._extract_js_expression(parsed, child, content, ts_lang, func_types)

            elif node_type in lang_defs.get('export', []):
                # Export statements wrapping functions/classes
                for sub in child.children:
                    if sub.type in func_types:
                        self._extract_function(parsed, sub, content, ts_lang)
                    elif sub.type in class_types:
                        self._extract_class(parsed, sub, content, ts_lang, func_types)

            elif node_type == 'lexical_declaration' and ts_lang in ('javascript', 'typescript'):
                # const myFunc = () => {} or const MyComponent = ...
                self._extract_js_const_function(parsed, child, content, ts_lang)

    def _extract_module_docstring(self, root, ts_lang: str, content: str) -> Optional[str]:
        """Extract module-level docstring/comment"""
        if not root.children:
            return None

        first = root.children[0]

        # Python: first expression_statement containing a string
        if ts_lang == 'python' and first.type == 'expression_statement':
            for sub in first.children:
                if sub.type == 'string':
                    text = content[sub.start_byte:sub.end_byte]
                    return text.strip('"\' \n')

        # JS/TS/Java/etc: leading block comment
        if first.type == 'comment':
            text = content[first.start_byte:first.end_byte]
            return self._clean_comment(text)

        return None

    def _extract_function(self, parsed: ParsedFile, node, content: str, ts_lang: str, parent_class: str = None):
        """Extract a function definition"""
        name = self._get_node_name(node, ts_lang)
        code = content[node.start_byte:node.end_byte]
        docstring = self._extract_docstring(node, ts_lang, content)

        unit = CodeUnit(
            unit_type='function',
            name=name,
            code=code,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=parsed.file_path,
            language=ts_lang,
            parent_class=parent_class,
            docstring=docstring,
        )
        parsed.functions.append(unit)

    def _extract_class(self, parsed: ParsedFile, node, content: str, ts_lang: str, func_types: set):
        """Extract a class with its methods"""
        name = self._get_node_name(node, ts_lang)
        code = content[node.start_byte:node.end_byte]
        docstring = self._extract_docstring(node, ts_lang, content)

        cls_unit = CodeUnit(
            unit_type='class',
            name=name,
            code=code,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=parsed.file_path,
            language=ts_lang,
            docstring=docstring,
        )

        # Extract methods inside the class body
        body = self._find_child_by_type(node, ['block', 'class_body', 'declaration_list',
                                                'field_declaration_list', 'body'])
        if body:
            for child in body.children:
                if child.type in func_types or child.type == 'method_definition':
                    method_name = self._get_node_name(child, ts_lang)
                    method_code = content[child.start_byte:child.end_byte]
                    method_doc = self._extract_docstring(child, ts_lang, content)

                    method_unit = CodeUnit(
                        unit_type='method',
                        name=method_name,
                        code=method_code,
                        line_start=child.start_point[0] + 1,
                        line_end=child.end_point[0] + 1,
                        file_path=parsed.file_path,
                        language=ts_lang,
                        parent_class=name,
                        docstring=method_doc,
                    )
                    cls_unit.children.append(method_unit)

                # Python decorated methods
                elif child.type == 'decorated_definition':
                    for sub in child.children:
                        if sub.type in func_types:
                            method_name = self._get_node_name(sub, ts_lang)
                            method_code = content[child.start_byte:child.end_byte]
                            method_doc = self._extract_docstring(sub, ts_lang, content)

                            method_unit = CodeUnit(
                                unit_type='method',
                                name=method_name,
                                code=method_code,
                                line_start=child.start_point[0] + 1,
                                line_end=child.end_point[0] + 1,
                                file_path=parsed.file_path,
                                language=ts_lang,
                                parent_class=name,
                                docstring=method_doc,
                            )
                            cls_unit.children.append(method_unit)

        parsed.classes.append(cls_unit)

    def _extract_import(self, parsed: ParsedFile, node, content: str, ts_lang: str):
        """Extract an import statement"""
        code = content[node.start_byte:node.end_byte]
        name = code.strip()

        parsed.imports.append(CodeUnit(
            unit_type='import',
            name=name,
            code=code,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            file_path=parsed.file_path,
            language=ts_lang,
        ))

    def _extract_js_expression(self, parsed: ParsedFile, node, content: str, ts_lang: str, func_types: set):
        """Handle JS/TS expression statements like module.exports = ..."""
        code = content[node.start_byte:node.end_byte]
        if 'module.exports' in code or 'exports.' in code:
            parsed.functions.append(CodeUnit(
                unit_type='export',
                name='module.exports',
                code=code,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                file_path=parsed.file_path,
                language=ts_lang,
            ))

    def _extract_js_const_function(self, parsed: ParsedFile, node, content: str, ts_lang: str):
        """Handle const myFunc = () => {} or const MyComponent = ..."""
        code = content[node.start_byte:node.end_byte]
        # Check if this contains an arrow function or function expression
        has_function = False
        name = None
        for child in node.children:
            if child.type == 'variable_declarator':
                for sub in child.children:
                    if sub.type == 'identifier':
                        name = content[sub.start_byte:sub.end_byte]
                    elif sub.type in ('arrow_function', 'function'):
                        has_function = True

        if has_function and name:
            parsed.functions.append(CodeUnit(
                unit_type='function',
                name=name,
                code=code,
                line_start=node.start_point[0] + 1,
                line_end=node.end_point[0] + 1,
                file_path=parsed.file_path,
                language=ts_lang,
            ))

    def _get_node_name(self, node, ts_lang: str) -> str:
        """Extract the name of a function/class node"""
        # Look for name/identifier child
        for child in node.children:
            if child.type in ('identifier', 'name', 'property_identifier',
                              'type_identifier', 'field_identifier'):
                return child.text.decode('utf-8') if isinstance(child.text, bytes) else str(child.text)

        # Fallback for some languages
        for child in node.children:
            if 'name' in child.type or 'identifier' in child.type:
                return child.text.decode('utf-8') if isinstance(child.text, bytes) else str(child.text)

        return '<anonymous>'

    def _extract_docstring(self, node, ts_lang: str, content: str) -> Optional[str]:
        """Extract docstring from a function/class node"""
        body = self._find_child_by_type(node, ['block', 'class_body', 'body',
                                                'statement_block', 'function_body'])
        if not body or not body.children:
            return None

        first_child = body.children[0]

        # Python: expression_statement > string
        if ts_lang == 'python' and first_child.type == 'expression_statement':
            for sub in first_child.children:
                if sub.type == 'string':
                    text = content[sub.start_byte:sub.end_byte]
                    return text.strip('"\' \n')

        # JS/TS/Java: leading comment block
        # Check for comment before the body
        prev = node.prev_sibling
        if prev and prev.type == 'comment':
            text = content[prev.start_byte:prev.end_byte]
            return self._clean_comment(text)

        return None

    def _find_child_by_type(self, node, types: list):
        """Find first child of given type(s)"""
        for child in node.children:
            if child.type in types:
                return child
        return None

    def _clean_comment(self, text: str) -> str:
        """Clean comment markers from text"""
        text = text.strip()
        # Block comments
        if text.startswith('/*'):
            text = text[2:]
        if text.endswith('*/'):
            text = text[:-2]
        # Line comments
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('//'):
                line = line[2:]
            elif line.startswith('#'):
                line = line[1:]
            elif line.startswith('*'):
                line = line[1:]
            lines.append(line.strip())
        return '\n'.join(lines).strip()

    # =========================================================================
    # REGEX FALLBACK PARSING
    # =========================================================================

    def _parse_with_regex(self, parsed: ParsedFile, content: str, ext: str):
        """Fallback regex-based parsing when tree-sitter is unavailable"""
        lines = content.split('\n')

        if ext in ('.py',):
            self._regex_parse_python(parsed, content, lines)
        elif ext in ('.js', '.jsx', '.ts', '.tsx'):
            self._regex_parse_javascript(parsed, content, lines)
        elif ext in ('.md', '.rst', '.txt'):
            # Documentation files: treat as single module
            parsed.functions.append(CodeUnit(
                unit_type='module',
                name=os.path.basename(parsed.file_path),
                code=content[:50000],
                line_start=1,
                line_end=len(lines),
                file_path=parsed.file_path,
                language=parsed.language,
            ))
        else:
            # Generic fallback: try to find function-like patterns
            self._regex_parse_generic(parsed, content, lines)

    def _regex_parse_python(self, parsed: ParsedFile, content: str, lines: List[str]):
        """Regex parse Python code"""
        # Find classes and functions
        class_pattern = re.compile(r'^class\s+(\w+)')
        func_pattern = re.compile(r'^(\s*)def\s+(\w+)')
        import_pattern = re.compile(r'^(import\s+|from\s+\S+\s+import\s+)')

        current_class = None
        current_class_indent = 0
        i = 0

        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()

            # Imports
            if import_pattern.match(stripped):
                parsed.imports.append(CodeUnit(
                    unit_type='import',
                    name=stripped.strip(),
                    code=stripped.strip(),
                    line_start=i + 1,
                    line_end=i + 1,
                    file_path=parsed.file_path,
                    language='python',
                ))
                i += 1
                continue

            indent = len(line) - len(line.lstrip())

            # Class
            m = class_pattern.match(stripped)
            if m and indent == 0:
                name = m.group(1)
                end = self._find_block_end_python(lines, i, indent)
                code = '\n'.join(lines[i:end + 1])

                cls_unit = CodeUnit(
                    unit_type='class',
                    name=name,
                    code=code,
                    line_start=i + 1,
                    line_end=end + 1,
                    file_path=parsed.file_path,
                    language='python',
                )
                current_class = name
                current_class_indent = indent

                # Find methods inside
                for j in range(i + 1, end + 1):
                    mline = lines[j]
                    fm = func_pattern.match(mline)
                    if fm:
                        method_indent = len(fm.group(1))
                        if method_indent > indent:
                            method_name = fm.group(2)
                            method_end = self._find_block_end_python(lines, j, method_indent)
                            method_code = '\n'.join(lines[j:method_end + 1])
                            cls_unit.children.append(CodeUnit(
                                unit_type='method',
                                name=method_name,
                                code=method_code,
                                line_start=j + 1,
                                line_end=method_end + 1,
                                file_path=parsed.file_path,
                                language='python',
                                parent_class=name,
                            ))

                parsed.classes.append(cls_unit)
                i = end + 1
                current_class = None
                continue

            # Top-level function
            fm = func_pattern.match(line)
            if fm and indent == 0:
                name = fm.group(2)
                end = self._find_block_end_python(lines, i, indent)
                code = '\n'.join(lines[i:end + 1])
                parsed.functions.append(CodeUnit(
                    unit_type='function',
                    name=name,
                    code=code,
                    line_start=i + 1,
                    line_end=end + 1,
                    file_path=parsed.file_path,
                    language='python',
                ))
                i = end + 1
                continue

            i += 1

    def _find_block_end_python(self, lines: List[str], start: int, indent: int) -> int:
        """Find end of a Python indented block"""
        end = start
        for j in range(start + 1, len(lines)):
            line = lines[j]
            if not line.strip():  # Skip empty lines
                end = j
                continue
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= indent:
                break
            end = j
        return end

    def _regex_parse_javascript(self, parsed: ParsedFile, content: str, lines: List[str]):
        """Regex parse JavaScript/TypeScript"""
        # Simple patterns for functions and classes
        func_patterns = [
            re.compile(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)'),
            re.compile(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\('),
            re.compile(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>'),
        ]
        class_pattern = re.compile(r'(?:export\s+)?class\s+(\w+)')
        import_pattern = re.compile(r'^import\s+')

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if import_pattern.match(line):
                parsed.imports.append(CodeUnit(
                    unit_type='import', name=line, code=line,
                    line_start=i + 1, line_end=i + 1,
                    file_path=parsed.file_path, language=parsed.language,
                ))
                i += 1
                continue

            m = class_pattern.match(line)
            if m:
                name = m.group(1)
                end = self._find_brace_block_end(lines, i)
                code = '\n'.join(lines[i:end + 1])
                parsed.classes.append(CodeUnit(
                    unit_type='class', name=name, code=code,
                    line_start=i + 1, line_end=end + 1,
                    file_path=parsed.file_path, language=parsed.language,
                ))
                i = end + 1
                continue

            for fp in func_patterns:
                m = fp.match(line)
                if m:
                    name = m.group(1)
                    end = self._find_brace_block_end(lines, i)
                    code = '\n'.join(lines[i:end + 1])
                    parsed.functions.append(CodeUnit(
                        unit_type='function', name=name, code=code,
                        line_start=i + 1, line_end=end + 1,
                        file_path=parsed.file_path, language=parsed.language,
                    ))
                    i = end + 1
                    break
            else:
                i += 1

    def _regex_parse_generic(self, parsed: ParsedFile, content: str, lines: List[str]):
        """Generic regex fallback: treat whole file as one unit"""
        parsed.functions.append(CodeUnit(
            unit_type='module',
            name=os.path.basename(parsed.file_path),
            code=content[:50000],
            line_start=1,
            line_end=len(lines),
            file_path=parsed.file_path,
            language=parsed.language,
        ))

    def _find_brace_block_end(self, lines: List[str], start: int) -> int:
        """Find end of a brace-delimited block { ... }"""
        depth = 0
        found_open = False
        for j in range(start, len(lines)):
            for ch in lines[j]:
                if ch == '{':
                    depth += 1
                    found_open = True
                elif ch == '}':
                    depth -= 1
                    if found_open and depth == 0:
                        return j
        return min(start + 50, len(lines) - 1)  # Fallback: 50 lines max

    # =========================================================================
    # CALL RELATIONSHIP EXTRACTION
    # =========================================================================

    def extract_call_relationships(self, parsed_files: List[ParsedFile]) -> Dict[str, List[str]]:
        """
        Extract function call relationships across all parsed files.

        Returns:
            Dict mapping "file:function" -> ["file:called_function", ...]
        """
        # Build a set of all known function/method names and their qualified paths
        known_functions: Dict[str, str] = {}  # name -> "file:name"
        for pf in parsed_files:
            for unit in pf.all_units:
                if unit.unit_type in ('function', 'method'):
                    key = f"{pf.file_path}:{unit.qualified_name}"
                    known_functions[unit.name] = key
                    known_functions[unit.qualified_name] = key

        # Find calls in each function's code
        calls: Dict[str, List[str]] = {}
        for pf in parsed_files:
            for unit in pf.all_units:
                if unit.unit_type in ('function', 'method', 'module'):
                    caller = f"{pf.file_path}:{unit.qualified_name}"
                    callees = set()

                    # Simple regex to find function calls: name(
                    call_pattern = re.compile(r'\b([a-zA-Z_]\w*(?:\.\w+)*)\s*\(')
                    for match in call_pattern.finditer(unit.code):
                        called_name = match.group(1)
                        # Skip self calls and common keywords
                        parts = called_name.split('.')
                        base_name = parts[-1]

                        if base_name in known_functions:
                            target = known_functions[base_name]
                            if target != caller:
                                callees.add(target)

                    if callees:
                        calls[caller] = sorted(callees)

        return calls

    def extract_import_graph(self, parsed_files: List[ParsedFile]) -> Dict[str, List[str]]:
        """
        Extract file-to-file import relationships.

        Returns:
            Dict mapping file_path -> [imported_file_paths]
        """
        # Build map of module names to file paths
        file_names: Dict[str, str] = {}
        for pf in parsed_files:
            base = os.path.basename(pf.file_path)
            name_no_ext = os.path.splitext(base)[0]
            file_names[name_no_ext] = pf.file_path
            file_names[base] = pf.file_path

        imports: Dict[str, List[str]] = {}
        for pf in parsed_files:
            deps = set()
            for imp in pf.imports:
                # Extract module name from import statement
                imp_text = imp.name
                # Python: from X import Y or import X
                for pattern in [
                    r'from\s+(\S+)\s+import',
                    r'import\s+(\S+)',
                    r'require\s*\(\s*[\'"]([^\'"]+)',
                    r'from\s+[\'"]([^\'"]+)',
                ]:
                    m = re.search(pattern, imp_text)
                    if m:
                        module = m.group(1).strip("'\"")
                        # Try to match to a known file
                        module_base = module.split('.')[-1].split('/')[-1]
                        if module_base in file_names:
                            target = file_names[module_base]
                            if target != pf.file_path:
                                deps.add(target)

            if deps:
                imports[pf.file_path] = sorted(deps)

        return imports
