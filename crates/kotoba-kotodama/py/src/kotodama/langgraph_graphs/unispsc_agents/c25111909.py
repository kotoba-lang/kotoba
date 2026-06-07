from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnchorState(TypedDict):
    material: str
    load_capacity: float
    status: str

def validate_specs(state: AnchorState):
    print(f'Validating anchor material: {state.get("material")}')
    return {'status': 'validated' if state.get('material') == '316 Stainless' else 'flagged'}

def final_approval(state: AnchorState):
    return {'status': 'approved'}

graph = StateGraph(AnchorState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', final_approval)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
