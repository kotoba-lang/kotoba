from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_name: str
    specs: dict
    is_approved: bool
    validation_log: List[str]

def validate_easel_specs(state: ProcurementState):
    log = []
    specs = state.get('specs', {})
    if specs.get('weight_capacity', 0) < 5:
        log.append('Weight capacity too low for professional use')
    return {'validation_log': log}

def approval_node(state: ProcurementState):
    return {'is_approved': len(state['validation_log']) == 0}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_easel_specs)
graph.add_node('approve', approval_node)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
