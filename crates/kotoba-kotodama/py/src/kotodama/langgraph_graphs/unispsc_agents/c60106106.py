from typing import TypedDict
from langgraph.graph import StateGraph, END

class HorticultureState(TypedDict):
    material_type: str
    compliance_checked: bool
    approved: bool

def validate_materials(state: HorticultureState):
    print(f'Validating: {state.get("material_type")}')
    return {'compliance_checked': True}

def approve_procurement(state: HorticultureState):
    return {'approved': state['compliance_checked']}

graph = StateGraph(HorticultureState)
graph.add_node('validate', validate_materials)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
