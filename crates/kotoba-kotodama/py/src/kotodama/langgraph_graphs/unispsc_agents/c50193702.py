from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodProcurementState(TypedDict):
    product_info: dict
    compliance_checks: list
    is_approved: bool

def validate_food_specs(state: FoodProcurementState):
    specs = state.get('product_info', {})
    checks = []
    if 'sanitary_certification' in specs:
        checks.append('certification_verified')
    return {'compliance_checks': checks, 'is_approved': len(checks) > 0}

graph = StateGraph(FoodProcurementState)
graph.add_node('validate', validate_food_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
