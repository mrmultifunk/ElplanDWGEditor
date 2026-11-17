#!/usr/bin/env python3
"""Kortlæg topniveau-definitioner og deres interne afhængigheder.

Rapporten ændrer ingen filer. Den bruges før hver flytning fra core_logic.py,
så stærkt sammenhængende funktionsgrupper kan opdages, før import-linter ser
en allerede opstået modulcykel.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from collections import Counter
from pathlib import Path


def _definitions(tree: ast.Module) -> dict[str, ast.AST]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _dependency_graph(definitions: dict[str, ast.AST]) -> dict[str, set[str]]:
    known = set(definitions)
    graph: dict[str, set[str]] = {}
    for name, node in definitions.items():
        referenced = {
            child.id
            for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
        }
        graph[name] = (referenced & known) - {name}
    return graph


def _strong_components(graph: dict[str, set[str]]) -> list[list[str]]:
    index = 0
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    components: list[list[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)
        for target in graph[node]:
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])
        if lowlinks[node] == indices[node]:
            component = []
            while True:
                target = stack.pop()
                on_stack.remove(target)
                component.append(target)
                if target == node:
                    break
            components.append(sorted(component))

    for node in sorted(graph):
        if node not in indices:
            visit(node)
    return sorted(components, key=lambda row: (-len(row), row))


def _module_assignment(definitions: dict[str, ast.AST], plan_path: Path | None):
    if plan_path is None or not plan_path.exists():
        return {}, [], [], []
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    completed_modules = sorted(
        str(name).strip()
        for name in plan.get("completed_modules", [])
        if str(name).strip()
    )
    assignment: dict[str, str] = {}
    duplicates = []
    for module in plan.get("modules", []):
        module_name = str(module.get("name", "") or "").strip()
        exact = {str(name) for name in module.get("names", [])}
        patterns = [re.compile(pattern) for pattern in module.get("patterns", [])]
        for name in definitions:
            if name not in exact and not any(pattern.fullmatch(name) for pattern in patterns):
                continue
            if name in assignment:
                duplicates.append({"name": name, "modules": [assignment[name], module_name]})
                continue
            assignment[name] = module_name
    unknown = sorted(
        name
        for module in plan.get("modules", [])
        for name in module.get("names", [])
        if name not in definitions
    )
    return assignment, duplicates, unknown, completed_modules


def build_report(path: Path, plan_path: Path | None = None) -> dict:
    source_text = path.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(path))
    definitions = _definitions(tree)
    graph = _dependency_graph(definitions)
    components = _strong_components(graph)
    cycles = [row for row in components if len(row) > 1]
    (
        assignment,
        duplicate_assignments,
        unknown_planned_names,
        completed_modules,
    ) = _module_assignment(definitions, plan_path)
    module_graph: dict[str, set[str]] = {
        module: set() for module in sorted(set(assignment.values()))
    }
    for source_name, targets in graph.items():
        source_module = assignment.get(source_name)
        if source_module is None:
            continue
        for target in targets:
            target_module = assignment.get(target)
            if target_module and target_module != source_module:
                module_graph[source_module].add(target_module)
    module_cycles = [row for row in _strong_components(module_graph) if len(row) > 1]
    incoming = Counter(target for targets in graph.values() for target in targets)
    outgoing = Counter({name: len(targets) for name, targets in graph.items()})
    return {
        "source": str(path),
        "lines": len(source_text.splitlines()),
        "top_level_definitions": len(definitions),
        "dependency_edges": sum(len(row) for row in graph.values()),
        "strongly_connected_cycles": cycles,
        "planned_modules": {
            module: sorted(name for name, target in assignment.items() if target == module)
            for module in sorted(set(assignment.values()))
        },
        "planned_definition_count": len(assignment),
        "completed_modules": completed_modules,
        "unassigned_definitions": sorted(set(definitions) - set(assignment)),
        "duplicate_assignments": duplicate_assignments,
        "unknown_planned_names": unknown_planned_names,
        "module_dependencies": {name: sorted(targets) for name, targets in module_graph.items()},
        "module_cycles": module_cycles,
        "most_referenced": [
            {"name": name, "incoming": count}
            for name, count in incoming.most_common(20)
        ],
        "most_dependent": [
            {"name": name, "outgoing": count}
            for name, count in outgoing.most_common(20)
        ],
        "dependencies": {name: sorted(targets) for name, targets in sorted(graph.items())},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path, default=Path("core_logic.py"))
    parser.add_argument("--json", action="store_true", help="Skriv hele rapporten som JSON")
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("tools/core_module_plan.json"),
        help="Foreløbig navne-/regexplan for de nye moduler",
    )
    args = parser.parse_args()
    report = build_report(args.source, args.plan)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"Kilde: {report['source']}")
    print(f"Linjer: {report['lines']}")
    print(f"Definitioner: {report['top_level_definitions']}")
    print(f"Interne afhængigheder: {report['dependency_edges']}")
    cycles = report["strongly_connected_cycles"]
    print(f"Stærkt sammenhængende cykler: {len(cycles)}")
    for component in cycles:
        print("  - " + ", ".join(component))
    print(f"Planlagte definitioner: {report['planned_definition_count']}")
    if report["completed_modules"]:
        print("Gennemførte moduler: " + ", ".join(report["completed_modules"]))
    print(f"Ikke fordelt endnu: {len(report['unassigned_definitions'])}")
    print(f"Modulcykler i den foreløbige plan: {len(report['module_cycles'])}")
    for component in report["module_cycles"]:
        print("  - " + " <-> ".join(component))
    if report["duplicate_assignments"]:
        print(f"Dobbeltfordelinger: {len(report['duplicate_assignments'])}")
    if report["unknown_planned_names"]:
        print(f"Navne i planen, som ikke findes: {len(report['unknown_planned_names'])}")
    print("Mest refererede definitioner:")
    for row in report["most_referenced"][:10]:
        print(f"  {row['incoming']:>3}  {row['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
