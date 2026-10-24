#!/usr/bin/env python3
"""flybrain export — convert topology to mainstream agent framework formats.

Supported formats:
  - langgraph: LangGraph StateGraph YAML (nodes + edges + state schema)
  - crewai: CrewAI crew YAML (agents + tasks + process)
  - autogen: AutoGen team JSON (agents + group chat config)

Usage:
  flybrain export <input.json> --format langgraph --output out.yaml
  flybrain export <input.json> --format crewai --output crew.yaml
  flybrain export <input.json> --format autogen --output team.json

This is a lightweight adapter — it converts the topology structure
(nodes, edges, roles, modules) into the framework's config format.
It does NOT include the full framework runtime; you still need to
install the target framework and wire up your own LLM providers.
"""

import argparse
import json
import sys
from pathlib import Path

# Framework-specific exporters


def export_langgraph(org: dict) -> dict:
    """Convert organism to LangGraph StateGraph format."""
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    modules = org.get("module_profiles", {})
    blueprint = org.get("blueprint", "unknown")

    # Build node functions (LangGraph expects callable names)
    node_funcs = []
    for n in nodes:
        node_id = n.get("id", "node")
        role = n.get("role", "agent")
        module = n.get("module", 0)
        # LangGraph node = function name
        func_name = f"node_{node_id.replace('.', '_')}"
        node_funcs.append({
            "id": node_id,
            "function": func_name,
            "role": role,
            "module": module,
            "profile": n.get("profile", ""),
            "task_hint": n.get("task_hint", ""),
        })

    # Build edges
    graph_edges = []
    for e in edges:
        if "source" in e and "target" in e:
            graph_edges.append({
                "source": e["source"],
                "target": e["target"],
                "condition": e.get("kind", "sequential"),
            })
        elif "from" in e and "to" in e:
            graph_edges.append({
                "source": e["from"],
                "target": e["to"],
                "condition": e.get("kind", "recurrent"),
            })

    return {
        "format": "langgraph",
        "version": "1.0",
        "blueprint": blueprint,
        "graph": {
            "state_schema": {
                "type": "dict",
                "fields": [
                    {"name": "input", "type": "str"},
                    {"name": "output", "type": "str"},
                    {"name": "history", "type": "list"},
                ],
            },
            "nodes": node_funcs,
            "edges": graph_edges,
            "entry_point": node_funcs[0]["function"] if node_funcs else None,
            "exit_point": node_funcs[-1]["function"] if node_funcs else None,
        },
        "modules": {
            str(m): {
                "name": m,
                "profile": modules.get(str(m), {}),
            }
            for m in modules
        },
        "metadata": {
            "source": "flybrain-connectome",
            "schema_version": org.get("schema_version", "1.2.1"),
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "generated_utc": org.get("generated_utc", ""),
        },
    }


def export_crewai(org: dict) -> dict:
    """Convert organism to CrewAI crew YAML format."""
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    modules = org.get("module_profiles", {})
    blueprint = org.get("blueprint", "unknown")

    # Build agents
    agents = []
    for n in nodes:
        node_id = n.get("id", "agent")
        role = n.get("role", "agent")
        module = n.get("module", 0)
        profile = n.get("profile", "")
        task_hint = n.get("task_hint", "")

        # CrewAI agent fields
        agent = {
            "role": role,
            "goal": f"Execute {task_hint} as {role} in module {module}",
            "backstory": f"Agent from flybrain blueprint '{blueprint}', module {module}",
            "role_id": node_id,
            "module": module,
            "profile": profile,
        }
        agents.append(agent)

    # Build tasks (one per module, grouping agents)
    tasks = []
    modules_in_order = sorted(set(n.get("module", 0) for n in nodes))
    for mod_id in modules_in_order:
        mod_agents = [a for a in agents if a.get("module") == mod_id]
        if not mod_agents:
            continue
        tasks.append({
            "name": f"module_{mod_id}_task",
            "description": f"Execute all tasks for module {mod_id}",
            "expected_output": f"Results from module {mod_id} agents",
            "agent": mod_agents[0],  # CrewAI requires one agent per task
            "agents": mod_agents,  # Extended: multiple agents per task
        })

    # Build process (sequential by default, use edges for conditional)
    process = "sequential"
    if edges:
        # Check if edges suggest hierarchical or consensus process
        edge_kinds = set()
        for e in edges:
            kind = e.get("kind", e.get("condition", ""))
            if kind:
                edge_kinds.add(kind)
        if "conditional" in edge_kinds:
            process = "hierarchical"

    return {
        "format": "crewai",
        "version": "1.0",
        "blueprint": blueprint,
        "crew": {
            "name": f"flybrain_{blueprint}",
            "description": f"Agent crew generated by flybrain-connectome from blueprint '{blueprint}'",
            "agents": agents,
            "tasks": tasks,
            "process": process,
            "verbose": True,
        },
        "modules": {
            str(m): modules.get(str(m), {})
            for m in modules
        },
        "metadata": {
            "source": "flybrain-connectome",
            "schema_version": org.get("schema_version", "1.2.1"),
            "n_agents": len(agents),
            "n_tasks": len(tasks),
            "generated_utc": org.get("generated_utc", ""),
        },
    }


def export_autogen(org: dict) -> dict:
    """Convert organism to AutoGen team JSON format."""
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    modules = org.get("module_profiles", {})
    blueprint = org.get("blueprint", "unknown")

    # Build agents
    agents = []
    for n in nodes:
        node_id = n.get("id", "agent")
        role = n.get("role", "agent")
        module = n.get("module", 0)
        profile = n.get("profile", "")
        task_hint = n.get("task_hint", "")

        # AutoGen agent fields
        agent = {
            "name": node_id,
            "role": role,
            "llm_config": {
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 1024,
            },
            "system_message": f"You are {role} in module {module}. Your task hint: {task_hint}. Profile: {profile}.",
            "module": module,
            "profile": profile,
        }
        agents.append(agent)

    # Build group chat config
    group_chat = {
        "message_kickoff": f"Start execution for blueprint '{blueprint}'",
        "speaker_selection_method": "auto",
        "max_round": 10,
        "allow_repeat_speaker": True,
    }

    return {
        "format": "autogen",
        "version": "1.0",
        "blueprint": blueprint,
        "team": {
            "name": f"flybrain_{blueprint}",
            "type": "RoundRobinGroupChat",
            "agents": agents,
            "group_chat": group_chat,
        },
        "edges": [
            {
                "source": e.get("source", e.get("from", "")),
                "target": e.get("target", e.get("to", "")),
                "kind": e.get("kind", e.get("condition", "")),
            }
            for e in edges
        ],
        "modules": {
            str(m): modules.get(str(m), {})
            for m in modules
        },
        "metadata": {
            "source": "flybrain-connectome",
            "schema_version": org.get("schema_version", "1.2.1"),
            "n_agents": len(agents),
            "n_edges": len(edges),
            "generated_utc": org.get("generated_utc", ""),
        },
    }


# Format registry

FORMATS = {
    "langgraph": export_langgraph,
    "crewai": export_crewai,
    "autogen": export_autogen,
}


def cmd_export(args) -> int:
    """Convert a topology JSON to a mainstream agent framework format."""
    # Load input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[export] ERROR: input file not found: {input_path}")
        return 1

    try:
        org = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[export] ERROR: cannot parse JSON: {e}")
        return 1

    # Validate format
    fmt = args.format.lower()
    if fmt not in FORMATS:
        print(f"[export] ERROR: unknown format '{fmt}'")
        print(f"[export] Supported formats: {', '.join(FORMATS.keys())}")
        return 1

    # Convert
    try:
        result = FORMATS[fmt](org)
    except Exception as e:
        print(f"[export] ERROR: conversion failed: {e}")
        return 1

    # Write output
    output_path = Path(args.output) if args.output else None
    if output_path is None:
        # Default output name
        stem = input_path.stem
        output_path = input_path.parent / f"{stem}.{fmt}"
        if fmt in ("langgraph", "crewai"):
            output_path = output_path.with_suffix(".yaml")
        else:
            output_path = output_path.with_suffix(".json")

    try:
        if fmt in ("langgraph", "crewai"):
            # YAML output (simple JSON-like YAML for readability)
            import yaml
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        else:
            # JSON output
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
    except ImportError:
        # yaml not available, fall back to JSON
        output_path = output_path.with_suffix(".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[export] ERROR: cannot write output: {e}")
        return 1

    # Report
    print(f"[export] {input_path.name} → {output_path.name}")
    print(f"[export] format: {fmt}")
    print(f"[export] nodes: {len(org.get('organism', {}).get('nodes', []))}")
    print(f"[export] edges: {len(org.get('organism', {}).get('edges', []))}")
    print(f"[export] output: {output_path}")
    return 0


# Add to parser
def add_export_parser(subparsers):
    """Add the 'export' subparser to the CLI."""
    s = subparsers.add_parser(
        "export",
        help="convert topology JSON to mainstream agent framework format",
        description=(
            "Convert a flybrain topology JSON to LangGraph, CrewAI, or AutoGen "
            "config format. This is a lightweight adapter — it converts the "
            "topology structure (nodes, edges, roles, modules) into the "
            "framework's config format, but does NOT include the full "
            "framework runtime."
        ),
    )
    s.add_argument("input", help="path to topology JSON file")
    s.add_argument("--format", required=True,
                   choices=["langgraph", "crewai", "autogen"],
                   help="target framework format")
    s.add_argument("--output", default=None,
                   help="output file path (default: <input_stem>.<format>)")
    s.set_defaults(func=cmd_export)
    return s
