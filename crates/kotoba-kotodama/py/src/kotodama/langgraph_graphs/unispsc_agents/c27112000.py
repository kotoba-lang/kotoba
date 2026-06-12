from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_type: str
    spec_verified: bool
    safety_approved: bool

def validate_tool_specs(state: ToolState):
    print(f'Validating specs for {state.get('tool_type')}')
    return {'spec_verified': True}

def safety_gate(state: ToolState):
    print('Checking safety standards')
    return {'safety_approved': True}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_tool_specs)
graph.add_node('safety', safety_gate)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
