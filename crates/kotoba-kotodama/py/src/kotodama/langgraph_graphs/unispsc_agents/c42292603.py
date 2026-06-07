from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    spec_compliance: bool
    sterilization_checked: bool
    certification_verified: bool

def validate_specs(state: SurgicalState):
    state['spec_compliance'] = True
    return state

def check_regulatory(state: SurgicalState):
    state['sterilization_checked'] = True
    return state

graph = StateGraph(SurgicalState)
graph.add_node('validate', validate_specs)
graph.add_node('regulatory', check_regulatory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'regulatory')
graph.add_edge('regulatory', END)
graph = graph.compile()
