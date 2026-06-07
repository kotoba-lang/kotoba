from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ControlModuleState(TypedDict):
    module_id: str
    specs: dict
    validation_passed: bool
    compilation_log: List[str]

def validate_specs(state: ControlModuleState):
    log = state.get("compilation_log", [])
    specs = state.get("specs", {})
    valid = "voltage" in specs and "protocols" in specs
    log.append(f"Validation: {valid}")
    return {"validation_passed": valid, "compilation_log": log}

def compile_module(state: ControlModuleState):
    log = state.get("compilation_log", [])
    log.append("Compiling logic for controller unit configuration")
    return {"compilation_log": log}

graph = StateGraph(ControlModuleState)
graph.add_node("validate", validate_specs)
graph.add_node("compile", compile_module)
graph.set_entry_point("validate")
graph.add_edge("validate", "compile")
graph.add_edge("compile", END)
graph = graph.compile()
