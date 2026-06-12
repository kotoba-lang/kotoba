from typing import TypedDict
from langgraph.graph import StateGraph, END

class BenderGraphState(TypedDict):
    tool_specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: BenderGraphState):
    specs = state.get('tool_specs', {})
    errors = []
    if not specs.get('max_diameter'): errors.append('Missing diameter limit')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def process_procurement(state: BenderGraphState):
    print('Processing procurement for Bender Tools...')
    return {'validation_passed': True}

graph = StateGraph(BenderGraphState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
