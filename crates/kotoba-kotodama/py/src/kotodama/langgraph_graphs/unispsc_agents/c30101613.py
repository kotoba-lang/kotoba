from typing import TypedDict
from langgraph.graph import StateGraph, END

class TinProcurementState(TypedDict):
    purity_level: float
    trace_elements: dict
    approved: bool

def validate_chemistry(state: TinProcurementState):
    # Business logic for tin bar procurement
    is_pure = state.get('purity_level', 0) >= 99.9
    return {'approved': is_pure}

workflow = StateGraph(TinProcurementState)
workflow.add_node('validation', validate_chemistry)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
