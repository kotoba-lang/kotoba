from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenApplianceState(TypedDict):
    model_name: str
    safety_check: bool
    compliance_docs: list

def validate_specs(state: KitchenApplianceState):
    state['safety_check'] = True
    return state

def check_compliance(state: KitchenApplianceState):
    state['compliance_docs'] = ['PSE', 'RoHS']
    return state

graph = StateGraph(KitchenApplianceState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
