"""XRPC façade routers for langgraph_server_app.

Each NSID family lives in a sibling module that exports an ``APIRouter``.
The langserver mounts them with the conventional ``/xrpc/{NSID}`` path
prefix per AT Protocol XRPC spec.
"""
