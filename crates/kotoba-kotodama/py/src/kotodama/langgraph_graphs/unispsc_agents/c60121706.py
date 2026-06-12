from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrintingBlockState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_block_specs(state: PrintingBlockState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('shore_hardness', 0) < 50:
        results.append('Hardness too low')
    state['validation_results'] = results
    state['is_approved'] = len(results) == 0
    return state

graph = StateGraph(PrintingBlockState)
graph.add_node('validate_specs', validate_block_specs)
graph.set_entry_point('validate_specs')
graph.add_edge('validate_specs', END)

graph = graph.compile()
