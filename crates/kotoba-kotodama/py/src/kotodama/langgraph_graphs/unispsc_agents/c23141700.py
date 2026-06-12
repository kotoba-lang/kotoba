from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AgitatorState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: AgitatorState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if 'motor_power_kw' not in specs:
        log.append("Missing motor_power_kw"); compliant = False
    return {"is_compliant": compliant, "validation_log": log}

def final_check(state: AgitatorState):
    return {"validation_log": state['validation_log'] + ["Final review complete"]}

graph = StateGraph(AgitatorState)
graph.add_node("validate", validate_specs)
graph.add_node("finalize", final_check)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
