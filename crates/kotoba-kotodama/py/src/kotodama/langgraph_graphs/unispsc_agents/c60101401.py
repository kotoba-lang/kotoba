from typing import TypedDict
from langgraph.graph import StateGraph, END

class BadgeState(TypedDict):
    order_id: str
    badge_type: str
    material_certified: bool

def validate_materials(state: BadgeState) -> BadgeState:
    if state.get('material_certified') is False:
        print('Compliance Alert: Material safety certification missing.')
    return state

def check_security_compliance(state: BadgeState) -> BadgeState:
    print(f'Validating security features for {state.get("badge_type")}')
    return state

graph = StateGraph(BadgeState)
graph.add_node('validate', validate_materials)
graph.add_node('security', check_security_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'security')
graph.add_edge('security', END)
graph = graph.compile()
