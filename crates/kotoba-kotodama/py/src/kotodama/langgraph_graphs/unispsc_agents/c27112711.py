from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_id: str
    specifications: dict
    is_compliant: bool

def validate_specs(state: ToolState):
    specs = state.get('specifications', {})
    required = ['operating_voltage', 'staple_size_range']
    is_compliant = all(key in specs for key in required)
    return {'is_compliant': is_compliant}

def route_by_compliance(state: ToolState):
    return 'validate' if not state.get('is_compliant') else END

workflow = StateGraph(ToolState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
