from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    tool_specs: dict
    is_validated: bool
    errors: List[str]

def validate_specs(state: ToolState):
    specs = state.get('tool_specs', {})
    errors = []
    if specs.get('tip_hardness_hrc', 0) < 55:
        errors.append('Insufficient tip hardness')

    return {'is_validated': len(errors) == 0, 'errors': errors}

def process_tool_req(state: ToolState):
    print('Processing procurement for intaglio tools...')
    return state

graph = StateGraph(ToolState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_tool_req)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
