from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FoodProcurementState(TypedDict):
    item_name: str
    batch_id: str
    quality_passed: bool
    compliance_risk: str

def validate_food_quality(state: FoodProcurementState):
    # Simulate inspection logic for perishables
    state['quality_passed'] = True
    return state

def check_compliance(state: FoodProcurementState):
    state['compliance_risk'] = 'low' if state['quality_passed'] else 'high'
    return state

graph = StateGraph(FoodProcurementState)
graph.add_node('inspection', validate_food_quality)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('inspection')
graph.add_edge('inspection', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
