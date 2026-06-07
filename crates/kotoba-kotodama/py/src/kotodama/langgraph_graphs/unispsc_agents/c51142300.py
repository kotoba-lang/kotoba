from langgraph.graph import StateGraph, END
from typing import TypedDict

class NarcoticState(TypedDict):
    batch_id: str
    is_compliant: bool
    verification_logs: list

def validate_regulatory(state: NarcoticState):
    # Simulate regulatory lookup
    state['is_compliant'] = True
    return {'verification_logs': ['FDA/EMA compliance verified']}

def check_cold_chain(state: NarcoticState):
    # Simulate cold chain monitoring
    return {'verification_logs': state['verification_logs'] + ['Cold chain integrity logged']}

graph = StateGraph(NarcoticState)
graph.add_node('regulatory', validate_regulatory)
graph.add_node('cold_chain', check_cold_chain)
graph.set_entry_point('regulatory')
graph.add_edge('regulatory', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()
