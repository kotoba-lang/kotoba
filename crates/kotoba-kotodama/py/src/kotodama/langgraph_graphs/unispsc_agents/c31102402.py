from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    part_specs: dict
    validation_error: str
    is_approved: bool

def validate_specs(state: CastingState):
    specs = state.get('part_specs', {})
    if 'grade' not in specs or 'tolerance' not in specs:
        return {'validation_error': 'Missing core specification fields', 'is_approved': False}
    return {'is_approved': True}

def process_workflow(state: CastingState):
    print('Initiating V-process foundry inspection sequence...')
    return state

graph = StateGraph(CastingState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)

# Compile the graph
graph = graph.compile()
