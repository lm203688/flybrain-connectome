# Module Factory: Variants, SwarmLabs Integration, and Market

> Added in v1.1.0. Covers the 8 new MCP tools for variant differentiation,
> SwarmLabs agent-team export, and virtual-organism marketplace.

---

## 1. Variant True Differentiation

Module variants produce **measurably different topologies**, not just labels.
Each variant carries real parameter overrides (`reservoir_density`,
`recurrent_pct`, `has_inhibition`) that are injected into `MODULE_PROFILES`
at composition time.

### Example: Compose an organism with sensory variants

```python
from module_registry import ModuleFactory

result = ModuleFactory.compose_organism({
    "modules": ["sensory", "memory", "motor", "integration"],
    "counts": {"sensory": 3},
    "variants": {"sensory": ["vision", "sound", "touch"]},
    "blueprint": "hierarchical_deep",
    "agents_per_module": 4,
    "seed": 42,
})

# result["stats"]["n_variants_applied"] == 3
# result["variants"] == {
#     "0": {"module": "sensory", "variant": "vision", "variant_profile": "sensory_vision"},
#     "1": {"module": "sensory", "variant": "sound",  "variant_profile": "sensory_sound"},
#     "2": {"module": "sensory", "variant": "touch",  "variant_profile": "sensory_touch"},
# }
```

### How variants differ from the base module

| Variant | `reservoir_density` | `recurrent_pct` | `has_inhibition` |
|---|---|---|---|
| `sensory_vision` | 0.60 | 0.35 | False |
| `sensory_sound` | 0.50 | 0.30 | False |
| `sensory_touch` | 0.45 | 0.25 | False |

The variant profiles are created dynamically: `base_params = base_spec.parameters.copy()`
then `base_params.update(base_spec.variants[vname])`. The resulting profile name
(`sensory_vision`) is matched against blueprint rules via prefix matching
(`startswith("sensory_")` → matches `sensory` blueprint rules).

### Blueprint prefix matching

```python
# In _apply_blueprint():
# A rule with from_prof="sensory" will match:
#   - "sensory"        (exact)
#   - "sensory_vision" (prefix: "sensory" + "_")
#   - "sensory_sound"  (prefix: "sensory" + "_")
```

---

## 2. SwarmLabs Agent-Team Integration

Convert any generated organism into a SwarmLabs multi-agent team spec.

### Example: Export to SwarmLabs

```python
from module_registry import ModuleFactory
from synthetic_bio_topology import build_swarmlabs_config

# Compose an organism
result = ModuleFactory.compose_organism({
    "modules": ["sensory", "memory", "motor", "integration", "attention"],
    "counts": {"sensory": 2, "memory": 1},
    "blueprint": "predictive_coding_v2",
    "agents_per_module": 4,
    "seed": 42,
})

# Convert to SwarmLabs config
swarm = build_swarmlabs_config(result["organism"])

# swarm contains:
# - schema_version: "1.2.1"
# - agents: [{id, name, module, profile, swarm_role, task_hint, capability, ...}]
# - edges: [{source, target, weight, semantic, ...}]
# - modules: [{id, name, profile, capability, members}]
# - leader: "coordinator"
# - guardrails: invariant definitions
# - validation: {ok: true, dangling_edges: 0, ...}
# - motif_provenance: full three-stage trace
# - prov_json: W3C PROV-JSON bundle (if dataprov installed)
```

### Module → Agent Role mapping

```python
from module_registry import ModuleFactory

roles = ModuleFactory.get_module_agent_roles()
# Returns a dict with 19 entries, e.g.:
# {
#     "sensory": {
#         "agent_role": "perceiver",
#         "task_hints": ["ingest", "perceive", "feature_extract"],
#         "capabilities": ["ingest", "perceive", "sense"],
#     },
#     "memory": {
#         "agent_role": "memory_bank",
#         "task_hints": ["remember", "retrieve", "store"],
#         "capabilities": ["remember", "recall", "store"],
#     },
#     ...
# }
```

### MCP tool: `organism_to_swarmlabs`

```json
{
    "name": "organism_to_swarmlabs",
    "inputSchema": {
        "properties": {
            "organism_path": {"type": "string", "description": "Path to organism JSON file"},
            "organism": {"type": "object", "description": "Or inline organism object"}
        }
    }
}
```

---

## 3. Virtual Organism Market

Local file-based CRUD for sharing custom module combinations.
Market directory: `male_cns/virtual_organisms/market/`

### Save a custom organism

```python
from module_registry import ModuleFactory

result = ModuleFactory.compose_organism({
    "modules": ["sensory", "motor", "integration"],
    "counts": {"sensory": 2, "motor": 1},
    "variants": {"sensory": ["vision", "sound"]},
    "blueprint": "deep_reasoning",
    "agents_per_module": 5,
    "seed": 123,
})

# Save to market
ModuleFactory.save_market_organism(
    name="my_cognitive_animal",
    organism=result["organism"],
    tags=["cognitive", "sensory-rich", "production-ready"],
    description="Multi-sensory organism with predictive coding",
    author="researcher_01",
)
```

### Load, list, search, rate, delete

```python
# Load by name
loaded = ModuleFactory.load_market_organism("my_cognitive_animal")

# List with tag filter + sort
organisms = ModuleFactory.list_market_organisms(
    tag="cognitive",
    sort="rating",  # "rating" | "name" | "nodes" | "created"
    limit=10,
)

# Search by keyword
results = ModuleFactory.search_market_organisms("cognitive sensory")

# Rate (1-5) with comment
rated = ModuleFactory.rate_market_organism("my_cognitive_animal", 5, "Excellent topology!")

# Delete
ModuleFactory.delete_market_organism("my_cognitive_animal")
```

### MCP tools

| Tool | Description |
|---|---|
| `save_market_organism` | Save a custom combination (auto-composes to get stats) |
| `load_market_organism` | Load a saved combination |
| `list_market_organisms` | List market with tag filter + sort |
| `rate_market_organism` | Rate 1-5 with comment (appends, recomputes average) |
| `search_market_organisms` | Keyword search across name/tags/description |
| `delete_market_organism` | Delete a combination |

---

## 4. Presets

10 built-in presets cover common use cases:

| Preset | Modules | Variants | Blueprint | Description |
|---|---|---|---|---|
| `minimal_reflex` | 2 | — | `fast_reflex` | Minimal sensory→motor reflex arc |
| `cognitive_animal` | 5 | — | `predictive_coding_v2` | Full cognitive pipeline |
| `multi_sensory_perceptor` | 3 | sensory×3 | `broad_explore` | Vision/sound/touch fusion |
| `swarm_controller` | 6 | — | `rl_actor_critic` | Multi-agent coordination |
| ... | ... | ... | ... | See `ModuleFactory.get_preset()` for all |

```python
# Apply a preset
result = ModuleFactory.apply_preset("cognitive_animal")

# Apply with overrides
result = ModuleFactory.apply_preset("cognitive_animal", {
    "seed": 42,
    "agents_per_module": 8,
})
```

---

## 5. Troubleshooting

**"unhashable type: list"** — Variant profile fields must use `list()` copies:
```python
"capability": list(base_spec.capabilities),
"task_hint_pool": list(base_spec.task_hints),
```

**"blueprint_edges_added == 0"** — Variant profiles need prefix matching in
`_apply_blueprint()`. Ensure `from_prof + "_"` check is present.

**"cycle detected" conflict** — Biological cycles are legitimate. Only cycles
involving 3+ distinct modules trigger conflicts (soft warning for 2-module loops).
