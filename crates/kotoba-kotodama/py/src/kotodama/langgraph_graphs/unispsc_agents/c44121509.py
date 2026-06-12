from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MailingBagState(TypedDict):
    dimensions: str
    material: str
    validated: bool

def validate_specs(state: MailingBagState):
    state['validated'] = all([state.get('dimensions'), state.get('material')])
    return state

graph = StateGraph(MailingBagState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
