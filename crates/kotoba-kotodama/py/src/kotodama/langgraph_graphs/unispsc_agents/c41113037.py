from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroplateState(TypedDict):
    instrument_id: str
    validation_passed: bool
    compliance_cert: bool

def validate_instrument(state: MicroplateState):
    state['validation_passed'] = bool(state.get('instrument_id'))
    return state

def check_compliance(state: MicroplateState):
    state['compliance_cert'] = True
    return state

graph = StateGraph(MicroplateState)
graph.add_node('validate', validate_instrument)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
