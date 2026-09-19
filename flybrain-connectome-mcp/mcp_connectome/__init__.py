"""flybrain-connectome-mcp: Drosophila MaleCNS connectome query/analysis toolkit.

Exposes the connectome as:
  (1) an MCP stdio server  -> `python -m mcp_connectome.server`
  (2) a zero-dependency HTTP API with apikey auth -> `python mcp_connectome/api_server.py`

Both share the same in-memory indexed query engine (mcp_connectome.core),
so any other project can call the connectome over stdio (MCP) or HTTP (apikey).
"""
__version__ = "1.0.0"
