from typing import TypedDict
from langgraph.graph import StateGraph, END

class PunchComponentState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_carbon_steel(state: PunchComponentState):
    specs = state.get('spec_data', {})
    required_keys = ['material_grade', 'tolerance']
    valid = all(k in specs for k in required_keys)
    return {'validation_passed': valid}

def process_workflow(state: PunchComponentState):
    print('Processing carbon steel punched component specifications...')
    return {'validation_passed': True}

graph = StateGraph(PunchComponentState)
graph.add_node('validate', validate_carbon_steel)
graph.add_node('process', process_workflow)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
