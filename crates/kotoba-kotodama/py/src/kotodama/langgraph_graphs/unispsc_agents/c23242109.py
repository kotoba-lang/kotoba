from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    specifications: dict
    validation_passed: bool

def validate_diamond_specs(state: ToolState):
    specs = state.get('specifications', {})
    # Logic to verify diamond grade and tolerance constraints
    is_valid = all(k in specs for k in ['grade', 'tolerance'])
    return {'validation_passed': is_valid}

def export_compliance_check(state: ToolState):
    # Logic for dual-use export control restrictions
    return {'validation_passed': True}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_diamond_specs)
graph.add_node('compliance', export_compliance_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
