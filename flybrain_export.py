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

For LangGraph, two modes are available:
  - Default (--format langgraph): emits a YAML config description.
  - --runnable: emits a real Python script that builds a StateGraph
    with a mock LLM backend, checkpointing, and OpenTelemetry tracing.
    Run it with `python generated_graph.py` — no API keys required.

CrewAI and AutoGen exports remain config-only adapters.
"""

import argparse
import json
import sys
from pathlib import Path

# Framework-specific exporters


def export_langgraph(org: dict) -> dict:
    """Convert organism to LangGraph StateGraph YAML config."""
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


def export_langgraph_runnable(org: dict) -> str:
    """Generate a self-contained Python script that builds a real LangGraph StateGraph.

    The generated script:
      1. Defines a TypedDict State with the topology's node fields.
      2. Creates a mock LLM backend (no API keys needed — deterministic echo + role prefix).
      3. Builds a StateGraph with one node function per topology node.
      4. Wires edges from the topology.
      5. Compiles the graph with MemorySaver checkpointing.
      6. Provides a `main()` entry point that runs the graph with a sample input.
      7. Includes optional OpenTelemetry trace span around each node.

    Usage of the generated file:
        python generated_graph.py          # runs the graph with sample input
        python generated_graph.py --trace  # enables OTel trace output
    """
    nodes = org.get("organism", {}).get("nodes", [])
    edges = org.get("organism", {}).get("edges", [])
    blueprint = org.get("blueprint", "unknown")
    n_nodes = len(nodes)
    n_edges = len(edges)

    # ---- Build the Python source ----
    lines = []
    lines.append('#!/usr/bin/env python3')
    lines.append(f'"""Generated by flybrain-connectome v3.01.2 — LangGraph runnable backend.')
    lines.append(f'Blueprint: {blueprint}  |  Nodes: {n_nodes}  |  Edges: {n_edges}')
    lines.append('')
    lines.append('This script is self-contained. It includes a mock LLM backend')
    lines.append('(no API keys required) so you can test the graph topology immediately:')
    lines.append('')
    lines.append('    python generated_graph.py            # run with mock LLM')
    lines.append('    python generated_graph.py --trace    # enable OTel trace')
    lines.append('')
    lines.append('To use a real LLM, replace MockLLMBackend with your provider:')
    lines.append('    - OpenAI:    from langchain_openai import ChatOpenAI')
    lines.append('    - Anthropic: from langchain_anthropic import ChatAnthropic')
    lines.append('    - Local:     from langchain_ollama import ChatOllama')
    lines.append('"""')
    lines.append('')
    lines.append('import argparse')
    lines.append('import json')
    lines.append('import sys')
    lines.append('from typing import TypedDict, Annotated')
    lines.append('')
    lines.append('# ---- State definition ----')
    lines.append('')
    lines.append('class State(TypedDict):')
    lines.append('    """Graph state — one field per topology node plus shared context."""')
    lines.append('    input: str')
    lines.append('    output: str')
    lines.append('    history: Annotated[list, "append"]')

    # Add a field per node for node-specific output
    for n in nodes:
        node_id = n.get("id", "node")
        safe_name = node_id.replace(".", "_").replace("/", "_")
        lines.append(f'    {safe_name}: str')
    lines.append('')
    lines.append('')

    # ---- Mock LLM Backend ----
    lines.append('# ---- Mock LLM Backend (no API keys needed) ----')
    lines.append('')
    lines.append('class MockLLMBackend:')
    lines.append('    """Deterministic mock LLM — echoes input with role prefix and node id."""')
    lines.append('')
    lines.append('    def __call__(self, prompt: str, role: str, node_id: str) -> str:')
    lines.append('        """Simulate an LLM call. Replace with a real provider for production."""')
    lines.append('        return f"[{role}::{node_id}] {prompt}"')
    lines.append('')
    lines.append('    @staticmethod')
    lines.append('    def is_mock() -> bool:')
    lines.append('        return True')
    lines.append('')
    lines.append('')

    # ---- OpenTelemetry (optional) ----
    lines.append('# ---- OpenTelemetry trace (optional, --trace flag) ----')
    lines.append('')
    lines.append('_OTEL_ENABLED = False')
    lines.append('_OTEL_TRACER = None')
    lines.append('')
    lines.append('def _enable_otel():')
    lines.append('    """Enable OpenTelemetry tracing (requires: pip install opentelemetry-api)."""')
    lines.append('    global _OTEL_ENABLED, _OTEL_TRACER')
    lines.append('    try:')
    lines.append('        from opentelemetry import trace')
    lines.append('        from opentelemetry.sdk.trace import TracerProvider')
    lines.append('        from opentelemetry.sdk.trace.export import ConsoleSpanExporter')
    lines.append('        from opentelemetry.sdk.trace.export import BatchSpanProcessor')
    lines.append('')
    lines.append('        provider = TracerProvider()')
    lines.append('        provider.add_span_processor(')
    lines.append('            BatchSpanProcessor(ConsoleSpanExporter())')
    lines.append('        )')
    lines.append('        trace.set_tracer_provider(provider)')
    lines.append('        _OTEL_TRACER = trace.get_tracer("flybrain-connectome")')
    lines.append('        _OTEL_ENABLED = True')
    lines.append('        print("[otel] OpenTelemetry tracing enabled")')
    lines.append('    except ImportError:')
    lines.append('        print("[otel] WARN: opentelemetry-api not installed — run: pip install opentelemetry-api opentelemetry-sdk")')
    lines.append('        _OTEL_ENABLED = False')
    lines.append('')
    lines.append('')

    # ---- Node functions ----
    lines.append('# ---- Node functions ----')
    lines.append('')
    lines.append('llm = MockLLMBackend()')
    lines.append('')

    for i, n in enumerate(nodes):
        node_id = n.get("id", f"node_{i}")
        role = n.get("role", "agent")
        module = n.get("module", 0)
        profile = n.get("profile", "")
        task_hint = n.get("task_hint", "")
        safe_name = node_id.replace(".", "_").replace("/", "_")
        func_name = f"node_{safe_name}"

        lines.append(f'def {func_name}(state: State) -> dict:')
        lines.append(f'    """Node function for {node_id} (role={role}, module={module})."""')
        lines.append(f'    if _OTEL_ENABLED:')
        lines.append(f'        with _OTEL_TRACER.start_as_current_span("{func_name}"):')
        lines.append(f'            return _run_{func_name}(state)')
        lines.append(f'    return _run_{func_name}(state)')
        lines.append('')
        lines.append(f'def _run_{func_name}(state: State) -> dict:')
        lines.append(f'    prompt = state.get("input", "")')
        lines.append(f'    result = llm(prompt, "{role}", "{node_id}")')
        lines.append(f'    return {{"{safe_name}": result, "output": result, "history": [result]}}')
        lines.append('')
        lines.append('')

    # ---- Graph builder ----
    lines.append('# ---- Graph builder ----')
    lines.append('')
    lines.append('def build_graph():')
    lines.append('    """Build and compile the LangGraph StateGraph from the flybrain topology."""')
    lines.append('    from langgraph.graph import StateGraph, START, END')
    lines.append('    from langgraph.checkpoint.memory import MemorySaver')
    lines.append('')
    lines.append('    graph = StateGraph(State)')

    # Add nodes
    for n in nodes:
        node_id = n.get("id", "node")
        safe_name = node_id.replace(".", "_").replace("/", "_")
        func_name = f"node_{safe_name}"
        lines.append(f'    graph.add_node("{safe_name}", {func_name})')

    lines.append('')

    # Add edges
    entry_added = False
    exit_added = False
    for e in edges:
        src = e.get("source", e.get("from", ""))
        tgt = e.get("target", e.get("to", ""))
        if not src or not tgt:
            continue
        safe_src = src.replace(".", "_").replace("/", "_")
        safe_tgt = tgt.replace(".", "_").replace("/", "_")
        lines.append(f'    graph.add_edge("{safe_src}", "{safe_tgt}")')

    # Entry point
    if nodes:
        first_node = nodes[0].get("id", "node")
        safe_first = first_node.replace(".", "_").replace("/", "_")
        lines.append(f'    graph.add_edge(START, "{safe_first}")')
        entry_added = True

    # Exit point
    if nodes:
        last_node = nodes[-1].get("id", "node")
        safe_last = last_node.replace(".", "_").replace("/", "_")
        lines.append(f'    graph.add_edge("{safe_last}", END)')
        exit_added = True

    lines.append('')
    lines.append('    # Compile with checkpointing')
    lines.append('    checkpointer = MemorySaver()')
    lines.append('    compiled = graph.compile(checkpointer=checkpointer)')
    lines.append('    return compiled')
    lines.append('')
    lines.append('')

    # ---- Main ----
    lines.append('# ---- Main entry point ----')
    lines.append('')
    lines.append('def main():')
    lines.append('    import argparse')
    lines.append('    parser = argparse.ArgumentParser(description="flybrain-connectome LangGraph runnable backend")')
    lines.append('    parser.add_argument("--trace", action="store_true", help="Enable OpenTelemetry tracing")')
    lines.append('    parser.add_argument("--input", type=str, default="hello flybrain", help="Initial input to the graph")')
    lines.append('    parser.add_argument("--thread", type=str, default="run-1", help="Checkpoint thread ID")')
    lines.append('    args = parser.parse_args()')
    lines.append('')
    lines.append('    if args.trace:')
    lines.append('        _enable_otel()')
    lines.append('')
    lines.append('    print(f"[flybrain] Building graph: {n_nodes} nodes, {n_edges} edges")')
    lines.append('    print(f"[flybrain] Blueprint: {blueprint}")')
    lines.append('    print(f"[flybrain] LLM backend: {type(llm).__name__}")')
    lines.append('    graph = build_graph()')
    lines.append('    print(f"[flybrain] Graph compiled with checkpointing")')
    lines.append('')
    lines.append('    config = {"configurable": {"thread_id": args.thread}}')
    lines.append('    initial_state = {"input": args.input, "output": "", "history": []}')
    lines.append('    result = graph.invoke(initial_state, config)')
    lines.append('')
    lines.append('    print(f"[flybrain] Execution complete")')
    lines.append('    print(f"[flybrain] Output: {result.get(\'output\', \'\')}")')
    lines.append('    print(f"[flybrain] History entries: {len(result.get(\'history\', []))}")')
    lines.append('    return result')
    lines.append('')
    lines.append('')
    lines.append('if __name__ == "__main__":')
    lines.append('    main()')
    lines.append('')

    return "\n".join(lines)


# Format registry

FORMATS = {
    "langgraph": export_langgraph,
    "crewai": export_crewai,
    "autogen": export_autogen,
}


def cmd_export(args) -> int:
    """Convert a topology JSON to a mainstream agent framework format.

    Supports --runnable for LangGraph: generates a real Python script
    with StateGraph + mock LLM backend + checkpointing + OTel trace.
    """
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"[export] ERROR: input file not found: {input_path}")
        return 1

    try:
        org = json.loads(input_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[export] ERROR: cannot parse JSON: {e}")
        return 1

    fmt = args.format.lower()
    runnable = getattr(args, "runnable", False)

    if fmt not in FORMATS:
        print(f"[export] ERROR: unknown format '{fmt}'")
        print(f"[export] Supported formats: {', '.join(FORMATS.keys())}")
        return 1

    if runnable and fmt != "langgraph":
        print(f"[export] ERROR: --runnable is only supported for --format langgraph")
        return 1

    # ---- Runnable mode: generate Python script ----
    if runnable:
        try:
            source = export_langgraph_runnable(org)
        except Exception as e:
            print(f"[export] ERROR: runnable generation failed: {e}")
            return 1

        output_path = Path(args.output) if args.output else None
        if output_path is None:
            stem = input_path.stem
            output_path = input_path.parent / f"{stem}_langgraph_run.py"

        try:
            output_path.write_text(source, encoding="utf-8")
        except Exception as e:
            print(f"[export] ERROR: cannot write output: {e}")
            return 1

        n_nodes = len(org.get("organism", {}).get("nodes", []))
        n_edges = len(org.get("organism", {}).get("edges", []))
        print(f"[export] {input_path.name} → {output_path.name}")
        print(f"[export] format: langgraph --runnable (Python script)")
        print(f"[export] nodes: {n_nodes}  |  edges: {n_edges}")
        print(f"[export] includes: StateGraph + MockLLMBackend + MemorySaver + OTel")
        print(f"[export] run with: python {output_path.name}")
        return 0

    # ---- YAML/JSON mode ----
    try:
        result = FORMATS[fmt](org)
    except Exception as e:
        print(f"[export] ERROR: conversion failed: {e}")
        return 1

    output_path = Path(args.output) if args.output else None
    if output_path is None:
        stem = input_path.stem
        output_path = input_path.parent / f"{stem}.{fmt}"
        if fmt in ("langgraph", "crewai"):
            output_path = output_path.with_suffix(".yaml")
        else:
            output_path = output_path.with_suffix(".json")

    try:
        if fmt in ("langgraph", "crewai"):
            import yaml
            with open(output_path, "w", encoding="utf-8") as f:
                yaml.dump(result, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
        else:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
    except ImportError:
        output_path = output_path.with_suffix(".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[export] ERROR: cannot write output: {e}")
        return 1

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
            "Convert a flybrain topology JSON to LangGraph, CrewAI, or AutoGen. "
            "For LangGraph, use --runnable to generate a real Python script with "
            "StateGraph, mock LLM backend, checkpointing, and OpenTelemetry tracing."
        ),
    )
    s.add_argument("input", help="path to topology JSON file")
    s.add_argument("--format", required=True,
                   choices=["langgraph", "crewai", "autogen"],
                   help="target framework format")
    s.add_argument("--runnable", action="store_true",
                   help="LangGraph only: generate a real Python script (not YAML config). "
                        "Includes MockLLMBackend (no API keys), MemorySaver checkpointing, "
                        "and optional --trace OTel tracing.")
    s.add_argument("--output", default=None,
                   help="output file path (default: <input_stem>.<format>)")
    s.set_defaults(func=cmd_export)
    return s
