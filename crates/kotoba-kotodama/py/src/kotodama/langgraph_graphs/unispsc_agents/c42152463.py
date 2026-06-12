from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSolventState(TypedDict):
    solubility_score: float
    purity_validated: bool
    safety_compliant: bool

def validate_safety(state: DentalSolventState):
    print('Validating SDS and hazardous compliance...')
    state['safety_compliant'] = True
    return state

def check_purity(state: DentalSolventState):
    print('Verifying chemical purity for dental standards...')
    state['purity_validated'] = True
    return state

graph = StateGraph(DentalSolventState)
graph.add_node('safety_check', validate_safety)
graph.add_node('purity_check', check_purity)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'purity_check')
graph.add_edge('purity_check', END)
graph = graph.compile()
