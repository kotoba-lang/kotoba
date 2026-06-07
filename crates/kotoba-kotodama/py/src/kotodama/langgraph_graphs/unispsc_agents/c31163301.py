from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ShimState(TypedDict):
    thickness_mm: float
    material: str
    compliance_checked: bool

def validate_specs(state: ShimState):
    print(f'Validating shim: {state.get("thickness_mm")}mm')
    return {'compliance_checked': state.get('thickness_mm', 0) > 0}

def approval_step(state: ShimState):
    print('Proceeding to procurement approval...')
    return {'compliance_checked': True}

graph = StateGraph(ShimState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
