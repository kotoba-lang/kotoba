from typing import TypedDict
from langgraph.graph import StateGraph, END

class OxytocinState(TypedDict):
    batch_id: str
    temp_logs: list
    validation_passed: bool

def validate_cold_chain(state: OxytocinState):
    # Simulate cold chain validation logic
    state['validation_passed'] = all(2 <= t <= 8 for t in state.get('temp_logs', []))
    return state

def procurement_workflow(state: OxytocinState):
    print(f'Processing procurement for batch {state.get('batch_id')}')
    return {'validation_passed': True}

graph = StateGraph(OxytocinState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('process', procurement_workflow)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'process')
graph.add_edge('process', END)
graph = graph.compile()
