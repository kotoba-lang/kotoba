from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_pruning_specs(state: ToolState) -> ToolState:
    specs = state.get('spec_data', {})
    # Logic check: Verify if cutting capacity is within industrial standards
    cap = specs.get('cutting_capacity_mm', 0)
    state['is_compliant'] = 5 <= cap <= 50
    return state

def process_procurement(state: ToolState) -> str:
    return 'compliant' if state['is_compliant'] else 'manual_review'

graph = StateGraph(ToolState)
graph.add_node('validate', validate_pruning_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
