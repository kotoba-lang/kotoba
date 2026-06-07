from typing import TypedDict
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material_type: str
    spec_compliant: bool
    validation_log: list

def validate_specs(state: PackagingState):
    log = []
    if not state.get('material_type'):
        log.append('Material type missing')
    return {'validation_log': log, 'spec_compliant': len(log) == 0}

def approval_step(state: PackagingState):
    return {'validation_log': state['validation_log'] + ['Procurement approved']}

graph = StateGraph(PackagingState)
graph.add_node('validator', validate_specs)
graph.add_node('approver', approval_step)
graph.add_edge('validator', 'approver')
graph.add_edge('approver', END)
graph.set_entry_point('validator')
graph = graph.compile()
