from typing import TypedDict
from langgraph.graph import StateGraph, END

class RubberChannelState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: RubberChannelState) -> RubberChannelState:
    specs = state.get('spec_data', {})
    required = ['hardness', 'dimensions']
    errors = []
    for field in required:
        if field not in specs:
            errors.append(f'Missing {field}')
    return {'validated': len(errors) == 0, 'error_log': errors}

graph = StateGraph(RubberChannelState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
