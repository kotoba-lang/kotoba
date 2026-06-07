from typing import TypedDict
from langgraph.graph import StateGraph, END
class AgriculturePartState(TypedDict):
    part_id: str
    material_specs: dict
    validation_status: bool
    compliant: bool
def validate_specs(state: AgriculturePartState):
    state['validation_status'] = True
    return {'validation_status': True}
def check_compliance(state: AgriculturePartState):
    state['compliant'] = state['validation_status']
    return {'compliant': True}
graph = StateGraph(AgriculturePartState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
