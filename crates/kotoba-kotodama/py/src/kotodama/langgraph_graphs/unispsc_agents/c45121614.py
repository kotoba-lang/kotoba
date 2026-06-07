from typing import TypedDict
from langgraph.graph import StateGraph, END

class RetrofitState(TypedDict):
    compatibility_check: bool
    compliance_validated: bool
    final_report: str

def check_compatibility(state: RetrofitState):
    state['compatibility_check'] = True
    return state

def validate_specs(state: RetrofitState):
    state['compliance_validated'] = True
    return state

graph = StateGraph(RetrofitState)
graph.add_node('check_compatibility', check_compatibility)
graph.add_node('validate_specs', validate_specs)
graph.set_entry_point('check_compatibility')
graph.add_edge('check_compatibility', 'validate_specs')
graph.add_edge('validate_specs', END)
graph = graph.compile()
