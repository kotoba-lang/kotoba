from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenEquipmentState(TypedDict):
    equipment_id: str
    spec_compliance: bool
    safety_check: bool

def validate_specs(state: KitchenEquipmentState):
    state['spec_compliance'] = True
    return state

def safety_assessment(state: KitchenEquipmentState):
    state['safety_check'] = True
    return state

graph = StateGraph(KitchenEquipmentState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_assessment)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
