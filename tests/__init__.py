"""P0-5 minimal test tree.

This is the P0-5 work package from the 2026-10-26 comprehensive upgrade
report. The pytest tree exists so `pip install -e .[dev] && pytest` is a
real command, not an aspirational one. The current smoke suite covers:

- scripts/_subprocess_util (P0-1 fix): UTF-8 encoding of subprocess output
- scripts/gen_project_status (P0-4 fix): JSON shape, count sanity, regen
- scripts/check_project_status (Gate 65): injection battery + happy path

The deeper suite (unit tests for the core algebra, integration tests for
HTTP/MCP contract, e2e tests for the audit CLI) remains a P1 work item.
The pytest tree here proves the plumbing works.
"""
