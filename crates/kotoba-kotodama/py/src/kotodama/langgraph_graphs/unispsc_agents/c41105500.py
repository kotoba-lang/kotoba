from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitState(TypedDict):
    kit_id: str
    purity_check: bool
    yield_validation: bool

def validate_purity(state: KitState):
    return {'purity_check': True}

def validate_yield(state: KitState):
    return {'yield_validation': True}

graph = StateGraph(KitState)
graph.add_node('purity', validate_purity)
graph.add_node('yield', validate_yield)
graph.add_edge('purity', 'yield')
graph.add_edge('yield', END)
graph.set_entry_point('purity')
graph = graph.compile()
