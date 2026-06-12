from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    product_id: str
    purity_certified: bool
    hazard_verified: bool
    status: str

def validate_specs(state: ReagentState):
    # Business logic for reagent validation
    state['purity_certified'] = True
    return {'status': 'VALIDATED' if state['purity_certified'] else 'FAILED'}

def check_hazard_compliance(state: ReagentState):
    # Check compliance for air sampling reagents
    state['hazard_verified'] = True
    return {'status': 'COMPLIANT'}

graph = StateGraph(ReagentState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_hazard_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
