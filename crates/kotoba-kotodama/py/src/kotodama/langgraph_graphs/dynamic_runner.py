"""Dynamic LangGraph executor for UNSPSC commodities using physical files."""

from typing import Any
import logging
import importlib

logger = logging.getLogger(__name__)

async def run_dynamic_workflow(commodity_code: str, payload: dict[str, Any]) -> dict[str, Any]:
    module_name = f"kotodama.langgraph_graphs.unispsc_agents.c{commodity_code}"
    
    try:
        # Dynamically import the generated python module for this commodity
        agent_module = importlib.import_module(module_name)
    except ImportError:
        # It's completely normal for a commodity to not have a custom agent yet.
        return {"ok": True, "result": {"status": "no_custom_agent_found"}}
    except Exception as exc:
        logger.exception(f"Failed to load custom agent for {commodity_code}")
        return {"ok": False, "error": f"Agent load failed: {exc}"}
    
    graph = getattr(agent_module, "graph", None)
    compile_graph = getattr(agent_module, "compile_graph", None)
    
    if not graph and not compile_graph:
        return {"ok": False, "error": f"Module {module_name} does not expose a 'graph' or 'compile_graph' object."}
    
    executable_graph = compile_graph if compile_graph else graph
    
    # If the graph hasn't been compiled yet, compile it.
    if hasattr(executable_graph, "compile"):
        executable_graph = executable_graph.compile()
        
    try:
        result = await executable_graph.ainvoke(payload)
        return {"ok": True, "result": result}
    except Exception as exc:
        logger.exception("Dynamic execution failed")
        return {"ok": False, "error": f"Dynamic execution failed: {exc}"}
