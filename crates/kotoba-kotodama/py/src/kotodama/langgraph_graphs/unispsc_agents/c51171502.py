from typing import TypedDict
from langgraph.graph import StateGraph, END

class MagaldrateState(TypedDict):
    purity_check: bool
    compliance_ok: bool

def validate_quality(state: MagaldrateState):
    return {'purity_check': True}

def check_regulations(state: MagaldrateState):
    return {'compliance_ok': True}

graph = StateGraph(MagaldrateState)
graph.add_node('quality', validate_quality)
graph.add_node('regulatory', check_regulations)
graph.set_entry_point('quality')
graph.add_edge('quality', 'regulatory')
graph.add_edge('regulatory', END)
graph = graph.compile()
