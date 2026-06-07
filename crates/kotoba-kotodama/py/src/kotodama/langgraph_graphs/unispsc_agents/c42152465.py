from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalLubricantState(TypedDict):
    lubricant_type: str
    compliance_checked: bool
    safety_grade: str

def validate_compliance(state: DentalLubricantState) -> DentalLubricantState:
    if state.get('safety_grade') == 'Medical':
        state['compliance_checked'] = True
    return state

def check_expiry(state: DentalLubricantState) -> DentalLubricantState:
    print('Verifying chemical batch expiry stability...')
    return state

graph = StateGraph(DentalLubricantState)
graph.add_node('validate', validate_compliance)
graph.add_node('expiry', check_expiry)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)
graph = graph.compile()
