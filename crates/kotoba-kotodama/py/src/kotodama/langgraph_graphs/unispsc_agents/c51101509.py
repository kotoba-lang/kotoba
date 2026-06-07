from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    commodity_code: str
    quality_docs: List[str]
    validation_passed: bool
    compliance_risk: str

def validate_gmp_docs(state: PharmState) -> PharmState:
    # Simulate inspection logic
    state['validation_passed'] = 'GMP' in ''.join(state.get('quality_docs', []))
    return state

def assess_risk(state: PharmState) -> PharmState:
    state['compliance_risk'] = 'HIGH' if not state['validation_passed'] else 'LOW'
    return state

graph = StateGraph(PharmState)
graph.add_node('validate', validate_gmp_docs)
graph.add_node('assess', assess_risk)
graph.add_edge('validate', 'assess')
graph.add_edge('assess', END)
graph.set_entry_point('validate')
graph = graph.compile()
