from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroscopeBulbState(TypedDict):
    part_number: str
    spec_check: bool
    approved: bool

def validate_specs(state: MicroscopeBulbState):
    # Simulate check: verify bulb voltage and compatibility
    state['spec_check'] = True if state.get('part_number') else False
    return state

def approval_step(state: MicroscopeBulbState):
    state['approved'] = state.get('spec_check', False)
    return state

graph = StateGraph(MicroscopeBulbState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
