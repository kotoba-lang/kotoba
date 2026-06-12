from langgraph.graph import StateGraph, END
from typing import TypedDict
class TractionSpec(TypedDict):
    device_id: str
    compliance_checked: bool
    sterilization_validated: bool
def validate_compliance(state: TractionSpec):
    state['compliance_checked'] = True
    return state
def validate_sterilization(state: TractionSpec):
    state['sterilization_validated'] = True
    return state
graph = StateGraph(TractionSpec)
graph.add_node('compliance', validate_compliance)
graph.add_node('sterilization', validate_sterilization)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'sterilization')
graph.add_edge('sterilization', END)
graph = graph.compile()
