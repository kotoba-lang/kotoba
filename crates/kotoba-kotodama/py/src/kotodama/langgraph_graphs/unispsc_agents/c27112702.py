from typing import TypedDict
from langgraph.graph import StateGraph, END

class BufferOrderState(TypedDict):
    order_id: str
    voltage_check: bool
    safety_verified: bool
    status: str

def validate_specs(state: BufferOrderState):
    # Simulate spec validation logic for power buffers
    state['voltage_check'] = True
    return {'voltage_check': True}

def safety_compliance(state: BufferOrderState):
    state['safety_verified'] = True
    return {'safety_verified': True}

graph = StateGraph(BufferOrderState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
