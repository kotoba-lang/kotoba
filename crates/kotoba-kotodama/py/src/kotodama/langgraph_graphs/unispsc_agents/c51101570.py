from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    commodity_code: str
    quality_check_passed: bool
    temperature_compliant: bool
    compliance_docs: List[str]

def validate_quality(state: ReagentState) -> ReagentState:
    state['quality_check_passed'] = True
    return state

def check_cold_chain(state: ReagentState) -> ReagentState:
    state['temperature_compliant'] = True
    return state

def verify_compliance(state: ReagentState) -> ReagentState:
    state['compliance_docs'] = ['COA', 'Safety_Data_Sheet']
    return state

graph = StateGraph(ReagentState)
graph.add_node('validate_quality', validate_quality)
graph.add_node('check_cold_chain', check_cold_chain)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('validate_quality')
graph.add_edge('validate_quality', 'check_cold_chain')
graph.add_edge('check_cold_chain', 'verify_compliance')
graph.add_edge('verify_compliance', END)

graph = graph.compile()
