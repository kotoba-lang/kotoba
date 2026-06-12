from typing import TypedDict
from langgraph.graph import StateGraph, END

class PhysicsCartState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_specs(state: PhysicsCartState):
    specs = state.get('spec_data', {})
    is_valid = all(key in specs for key in ['load_capacity', 'dimensions'])
    print('Validating physics cart specifications...')
    return {'validation_passed': is_valid}

def process_workflow(state: PhysicsCartState):
    print('Processing cart quality check protocols...')
    return {'validation_passed': state.get('validation_passed', False)}

graph = StateGraph(PhysicsCartState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_workflow)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')

graph = graph.compile()
