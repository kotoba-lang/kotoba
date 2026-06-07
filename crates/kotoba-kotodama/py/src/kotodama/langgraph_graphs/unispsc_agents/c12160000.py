from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    safety_clearance: bool
    compliance_report: str

def validate_safety_protocols(state: ChemicalState) -> ChemicalState:
    # Simulate hazard assessment
    state['safety_clearance'] = True
    return state

def generate_compliance_docs(state: ChemicalState) -> ChemicalState:
    state['compliance_report'] = 'Compliance verified against ISO/IEC standards.'
    return state

graph = StateGraph(ChemicalState)
graph.add_node('safety_check', validate_safety_protocols)
graph.add_node('compliance', generate_compliance_docs)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
