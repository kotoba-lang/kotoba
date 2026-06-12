"""LangGraph generic BPMN-contract runner.

BPMN XML is kept as a contract and audit artifact, but execution is pod-side
LangGraph/Pregel/LangChain handler dispatch. This module deliberately avoids
legacy broker or in-process BPMN engine imports.
"""
import importlib
import inspect
import json
import logging
from pathlib import Path
from typing import TypedDict, Any
from xml.etree import ElementTree as ET

from langgraph.graph import StateGraph, END

logger = logging.getLogger(__name__)

class RegistryWorker:
    def __init__(self):
        self.tasks = {}

    def task(self, task_type: str, **kwargs):
        def decorator(f):
            self.tasks[task_type] = f
            return f
        return decorator

registry = RegistryWorker()

def _load_primitives():
    """Dynamically load all primitives to populate the global registry."""
    import kotodama.primitives
    pkg_path = Path(kotodama.primitives.__file__).parent
    for p in pkg_path.glob("*.py"):
        if p.name.startswith("_"):
            continue
        mod_name = f"kotodama.primitives.{p.stem}"
        try:
            mod = importlib.import_module(mod_name)
            if hasattr(mod, "register"):
                sig = inspect.signature(mod.register)
                kwargs = {}
                if "timeout_ms" in sig.parameters:
                    kwargs["timeout_ms"] = 60000
                if "worker" in sig.parameters:
                    kwargs["worker"] = registry
                elif "app" in sig.parameters:
                    kwargs["app"] = registry
                else:
                    kwargs["worker"] = registry

                try:
                    mod.register(**kwargs)
                except TypeError:
                    # Fallback for signatures like `def register(worker)`
                    mod.register(registry)
        except Exception as e:
            logger.debug(f"Failed to register {mod_name} in generic runner: {e}")

_load_primitives()

class GenericBpmnState(TypedDict, total=False):
    bpmn_process_id: str
    variables: dict[str, Any]
    runner_state_json: str
    completed: bool
    error: str
    executed: list[dict[str, Any]]


_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
_ZEEBE_NS = "http://camunda.org/schema/zeebe/1.0"
_CAMUNDA_NS = "http://camunda.org/schema/1.0/bpmn"


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _service_task_type(task: ET.Element) -> str:
    """Extract a service-task handler id from BPMN extension attributes."""
    for child in task.iter():
        if _tag_name(child.tag) != "taskDefinition":
            continue
        task_type = child.attrib.get("type") or child.attrib.get(f"{{{_ZEEBE_NS}}}type")
        if task_type:
            return task_type
    for attr in (
        f"{{{_ZEEBE_NS}}}type",
        f"{{{_CAMUNDA_NS}}}type",
        "type",
        "implementation",
        "name",
        "id",
    ):
        value = task.attrib.get(attr)
        if value:
            return value
    return task.attrib.get("id", "")


def _load_bpmn_contract(bpmn_process_id: str) -> str | None:
    from kotodama.kotoba_datomic import get_kotoba_client

    client = get_kotoba_client()
    # R0: Filtering for status='active' and ordering by version DESC is done in Python.
    rows = client.select_where(
        "vertex_bpmn_process_def", "bpmn_process_id", bpmn_process_id, columns=["xml", "status", "version"]
    )

    active_rows = [r for r in rows if r.get("status") == "active"]
    if not active_rows:
        return None

    # Sort by version in descending order and get the first one (equivalent to ORDER BY version DESC LIMIT 1)
    active_rows.sort(key=lambda x: x.get("version", 0), reverse=True)
    row = active_rows[0]

    xml_content = row.get("xml")
    if isinstance(xml_content, bytes):
        return xml_content.decode("utf-8")
    return str(xml_content) if xml_content else None

def engine_step(state: GenericBpmnState) -> dict:
    """Execute service-task handlers from a BPMN contract in document order."""
    bpmn_process_id = state.get("bpmn_process_id")
    if not bpmn_process_id:
        return {"error": "Missing bpmn_process_id", "completed": True}

    xml_content = _load_bpmn_contract(bpmn_process_id)
    if not xml_content:
        return {"error": f"BPMN process {bpmn_process_id} not found in DB or xml is empty", "completed": True}

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        return {"error": f"BPMN XML parse failed: {exc}", "completed": True}

    variables: dict[str, Any] = dict(state.get("variables") or {})
    executed: list[dict[str, Any]] = list(state.get("executed") or [])
    completed_ids = {item.get("id") for item in executed}

    service_tasks = [
        node for node in root.iter()
        if _tag_name(node.tag) in {"serviceTask", "businessRuleTask", "sendTask", "scriptTask"}
    ]
    for task in service_tasks:
        task_id = task.attrib.get("id") or task.attrib.get("name") or _service_task_type(task)
        if task_id in completed_ids:
            continue
        task_type = _service_task_type(task)
        handler = registry.tasks.get(task_type)
        if handler is None:
            logger.warning("No LangServer handler registered for BPMN task type: %s", task_type)
            return {
                "variables": variables,
                "runner_state_json": json.dumps({"completedTaskIds": list(completed_ids)}),
                "executed": executed,
                "completed": False,
                "error": f"No LangServer handler registered for task type {task_type!r}",
            }
        try:
            payload = {"variables": variables}
            if inspect.iscoroutinefunction(handler):
                import asyncio
                result = asyncio.run(handler(**payload))
            else:
                result = handler(**payload)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error executing task %s", task_type)
            return {"error": f"Task {task_type} failed: {exc}", "completed": True}

        if isinstance(result, dict):
            variables.update(result)
        executed.append({"id": task_id, "taskType": task_type, "ok": isinstance(result, dict)})
        completed_ids.add(task_id)

    next_json = json.dumps({"completedTaskIds": list(completed_ids)})
    return {
        "variables": variables,
        "runner_state_json": next_json,
        "executed": executed,
        "completed": True,
        "error": None
    }

def build_graph():
    builder = StateGraph(GenericBpmnState)
    builder.add_node("engine_step", engine_step)
    builder.set_entry_point("engine_step")
    builder.add_edge("engine_step", END)
    return builder.compile()

generic_bpmn_runner_graph = build_graph()
