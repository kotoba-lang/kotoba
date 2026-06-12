from typing import TypedDict
from langgraph.graph import StateGraph, END

class CannulaState(TypedDict):
    spec_compliance: bool
    sterility_check: bool

def validate_specs(state: CannulaState):
    state['spec_compliance'] = True
    return state

def check_sterility(state: CannulaState):
    state['sterility_check'] = True
    return state

graph = StateGraph(CannulaState)
graph.add_node("validate", validate_specs)
graph.add_node("sterility", check_sterility)
graph.set_entry_point("validate")
graph.add_edge("validate", "sterility")
graph.add_edge("sterility", END)
graph = graph.compile()
