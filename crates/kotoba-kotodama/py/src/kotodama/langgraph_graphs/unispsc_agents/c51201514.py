from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicamentState(TypedDict):
    batch_id: str
    purity_check: bool
    temp_log_validated: bool

def validate_purity(state: MedicamentState):
    state['purity_check'] = True
    return state

def validate_storage(state: MedicamentState):
    state['temp_log_validated'] = True
    return state

graph = StateGraph(MedicamentState)
graph.add_node('check_purity', validate_purity)
graph.add_node('check_storage', validate_storage)
graph.set_entry_point('check_purity')
graph.add_edge('check_purity', 'check_storage')
graph.add_edge('check_storage', END)
graph = graph.compile()
