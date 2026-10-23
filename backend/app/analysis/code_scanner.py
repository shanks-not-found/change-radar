"""
Code Scanner for StackSignal.

Uses Python `ast` to statically inspect project code, recording which packages,
imported symbols, functions, classes, and attributes are called or referenced,
along with exact file paths, 1-indexed line numbers, and code snippets.
Safely skips unparseable or syntax-errored files without crashing.
"""

import ast
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from app.schemas import CodeReference
from app.analysis.package_map import get_import_names_for_package, normalize_package_name

logger = logging.getLogger(__name__)

class CodeUsageVisitor(ast.NodeVisitor):
    def __init__(self, rel_path: str, source_lines: List[str]) -> None:
        self.rel_path = rel_path
        self.source_lines = source_lines
        
        # Local alias mappings:
        # alias_name -> (module_root, full_symbol_or_path)
        self.alias_map: Dict[str, Tuple[str, str]] = {}
        
        # Collected references: list of (module_root, CodeReference)
        self.references: List[Tuple[str, CodeReference]] = []

    def _get_snippet(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            local_name = alias.asname or alias.name
            self.alias_map[local_name] = (root_mod, alias.name)
            
            snippet = self._get_snippet(node.lineno)
            ref = CodeReference(
                file_path=self.rel_path,
                line_number=node.lineno,
                snippet=snippet,
                symbol=alias.name,
            )
            self.references.append((root_mod, ref))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not node.module:
            return
        root_mod = node.module.split(".")[0]
        for alias in node.names:
            local_name = alias.asname or alias.name
            full_symbol = f"{node.module}.{alias.name}"
            self.alias_map[local_name] = (root_mod, full_symbol)
            
            snippet = self._get_snippet(node.lineno)
            ref = CodeReference(
                file_path=self.rel_path,
                line_number=node.lineno,
                snippet=snippet,
                symbol=alias.name,
            )
            self.references.append((root_mod, ref))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct call of imported name (e.g. FastAPI())
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in self.alias_map:
                root_mod, full_path = self.alias_map[func_name]
                symbol = full_path.split(".")[-1]
                snippet = self._get_snippet(node.lineno)
                self.references.append((
                    root_mod,
                    CodeReference(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        snippet=snippet,
                        symbol=symbol,
                    )
                ))
        # Check attribute call (e.g. app.add_middleware() or client.chat())
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if isinstance(node.func.value, ast.Name) and node.func.value.id in self.alias_map:
                root_mod, full_path = self.alias_map[node.func.value.id]
                snippet = self._get_snippet(node.lineno)
                self.references.append((
                    root_mod,
                    CodeReference(
                        file_path=self.rel_path,
                        line_number=node.lineno,
                        snippet=snippet,
                        symbol=f"{attr_name}",
                    )
                ))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # Catch attribute usage like MyModel.Config or settings.field
        if isinstance(node.value, ast.Name) and node.value.id in self.alias_map:
            root_mod, full_path = self.alias_map[node.value.id]
            snippet = self._get_snippet(node.lineno)
            self.references.append((
                root_mod,
                CodeReference(
                    file_path=self.rel_path,
                    line_number=node.lineno,
                    snippet=snippet,
                    symbol=node.attr,
                )
            ))
        self.generic_visit(node)


def scan_file(file_path: Path, project_root: Path) -> List[Tuple[str, CodeReference]]:
    """Statically parses a single python file and extracts all symbol references."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"Unable to read file {file_path}: {e}")
        return []

    try:
        tree = ast.parse(content, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError, ValueError) as e:
        logger.debug(f"Skipping unparseable file {file_path}: {e}")
        return []

    try:
        rel_path = str(file_path.relative_to(project_root)).replace("\\", "/")
    except ValueError:
        rel_path = file_path.name

    lines = content.splitlines()
    visitor = CodeUsageVisitor(rel_path, lines)
    visitor.visit(tree)
    return visitor.references


def scan_project_code(
    project_dir: Path, packages: List[str]
) -> Dict[str, List[CodeReference]]:
    """
    Scans all Python source files in the project directory.
    Maps detected symbol references to the requested package dependencies.
    """
    ignored_dirs = {".venv", "venv", "node_modules", ".git", "__pycache__", "build", "dist", ".tox"}

    # Build reverse map: root_module_name -> package_name
    mod_to_pkg: Dict[str, str] = {}
    for pkg in packages:
        norm_pkg = normalize_package_name(pkg)
        import_names = get_import_names_for_package(norm_pkg)
        for imp in import_names:
            mod_to_pkg[imp.lower()] = norm_pkg

    # Collect python files
    py_files: List[Path] = []
    for p in project_dir.rglob("*.py"):
        if not any(part in ignored_dirs for part in p.parts):
            py_files.append(p)

    results: Dict[str, List[CodeReference]] = {normalize_package_name(pkg): [] for pkg in packages}

    for py_file in py_files:
        refs = scan_file(py_file, project_dir)
        for root_mod, ref in refs:
            norm_mod = root_mod.lower().replace("_", "-")
            direct_pkg = mod_to_pkg.get(root_mod.lower()) or mod_to_pkg.get(norm_mod)
            if direct_pkg and direct_pkg in results:
                # Deduplicate exact file+line+symbol
                existing = results[direct_pkg]
                if not any(e.file_path == ref.file_path and e.line_number == ref.line_number and e.symbol == ref.symbol for e in existing):
                    existing.append(ref)

    return results
