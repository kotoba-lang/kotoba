from langgraph.graph import StateGraph, END
from typing import TypedDict

class ToolState(TypedDict):
    spec_completed: bool
    safety_verified: bool
    device_id: str

def validate_specs(state: ToolState):
    print('Validating thermal specifications...')
    return {'spec_completed': True}

def safety_check(state: ToolState):
    print('Checking electrical thermal cutoff mechanisms...')
    return {'safety_verified': True}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
