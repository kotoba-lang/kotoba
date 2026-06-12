from typing import TypedDict
from langgraph.graph import StateGraph, END

class HcgState(TypedDict):
    batch_id: str
    temperature_check: bool
    purity_validated: bool

def validate_cold_chain(state: HcgState):
    return {'temperature_check': True}

def validate_biochemistry(state: HcgState):
    return {'purity_validated': True}

graph = StateGraph(HcgState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('biochemistry', validate_biochemistry)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'biochemistry')
graph.add_edge('biochemistry', END)
graph = graph.compile()
