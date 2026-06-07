from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ViscoState(TypedDict):
    product_id: str
    purity_cert: bool
    sterility_check: bool
    risk_score: float

def validate_purity(state: ViscoState):
    state['purity_cert'] = True
    return state

def check_sterility(state: ViscoState):
    state['sterility_check'] = True
    return state

graph = StateGraph(ViscoState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_sterility', check_sterility)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'check_sterility')
graph.add_edge('check_sterility', END)
graph = graph.compile()
