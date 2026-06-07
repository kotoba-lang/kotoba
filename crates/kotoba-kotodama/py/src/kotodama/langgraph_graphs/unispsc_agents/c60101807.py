from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    specs: List[str]
    validated: bool

def validate_beads(state: ProcurementState):
    print(f'Validating specs for {state[item_name]}')
    state['validated'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_beads)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
