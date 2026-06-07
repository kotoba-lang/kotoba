from typing import TypedDict
from langgraph.graph import StateGraph, END

class BreadMachineState(TypedDict):
    specs: dict
    approved: bool
    validation_errors: list

def validate_specs(state: BreadMachineState):
    errors = []
    if 'power' not in state['specs']: errors.append('Missing power output')
    if 'certification' not in state['specs']: errors.append('Missing safety certification')
    return {'validation_errors': errors, 'approved': len(errors) == 0}

def route(state: BreadMachineState):
    return 'process' if state['approved'] else END

graph = StateGraph(BreadMachineState)
graph.add_node('validate', validate_specs)
graph.add_edge('process', END)
graph.set_entry_point('validate')

graph = graph.compile()
