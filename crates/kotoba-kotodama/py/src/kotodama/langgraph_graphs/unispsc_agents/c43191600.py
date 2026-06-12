from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class DevToolState(TypedDict):
    tool_name: str
    validation_tasks: List[str]
    is_compliant: bool

def validate_tool(state: DevToolState) -> DevToolState:
    # Simplified mock validation logic
    tasks = state.get('validation_tasks', [])
    is_compliant = len(tasks) > 0
    return {'is_compliant': is_compliant}

def finalize_setup(state: DevToolState) -> DevToolState:
    return {'is_compliant': True}

graph = StateGraph(DevToolState)
graph.add_node('validate', validate_tool)
graph.add_node('finalize', finalize_setup)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
