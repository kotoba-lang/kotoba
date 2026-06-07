from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    spec_compliance: bool
    safety_check: bool

def validate_tool(state: ToolState):
    # Simulate CAD specs or power compliance check
    compliance = state.get('tool_id', '').startswith('IND-')
    return {'spec_compliance': compliance}

def safety_audit(state: ToolState):
    return {'safety_check': True}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_tool)
graph.add_node('safety', safety_audit)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
