from typing import TypedDict
from langgraph.graph import StateGraph, END

class EPOState(TypedDict):
    batch_id: str
    temp_log_range: str
    is_validated: bool

def validate_cold_chain(state: EPOState):
    state['is_validated'] = '2-8C' in state.get('temp_log_range', '')
    return state

def process_batch(state: EPOState):
    print(f'Processing Batch: {state.get("batch_id")}')
    return state

graph = StateGraph(EPOState)
graph.add_node('validate', validate_cold_chain)
graph.add_node('process', process_batch)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
