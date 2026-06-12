from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    spec_sheet: dict
    validation_passed: bool
    log: list

def validate_resin_spec(state: ResinState):
    log = state.get('log', [])
    spec = state.get('spec_sheet', {})
    passed = spec.get('purity', 0) >= 99.9
    log.append('Spec validation completed')
    return {'validation_passed': passed, 'log': log}

def process_resin_workflow(state: ResinState):
    log = state.get('log', [])
    log.append('Initializing robotics assembly injection')
    return {'log': log}

builder = StateGraph(ResinState)
builder.add_node('validate', validate_resin_spec)
builder.add_node('process', process_resin_workflow)
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validate')
graph = builder.compile()
