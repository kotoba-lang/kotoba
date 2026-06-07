from typing import TypedDict
from langgraph.graph import StateGraph, END

class CheeseState(TypedDict):
    temp_log: list
    is_compliant: bool

def validate_cold_chain(state: CheeseState):
    # Simulate cold chain validation logic
    temp = state.get('temp_log', [])
    valid = all(t <= 5 for t in temp)
    return {'is_compliant': valid}

def finish(state: CheeseState):
    return {'is_compliant': state['is_compliant']}

graph = StateGraph(CheeseState)
graph.add_node('validate', validate_cold_chain)
graph.add_node('finish', finish)
graph.add_edge('validate', 'finish')
graph.add_edge('finish', END)
graph.set_entry_point('validate')
graph = graph.compile()
