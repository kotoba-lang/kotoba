from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_certificate_spec(state: State):
    req = state.get('spec_data', {})
    # Ensure paper quality meets archival standard for religious records
    passed = req.get('paper_weight_gsm', 0) >= 120 and req.get('archival_quality_rating', 'low') != 'low'
    return {'validation_passed': passed}

def printer_workflow(state: State):
    print('Initiating printing process for religious certificates...')
    return {'validation_passed': True}

graph = StateGraph(State)
graph.add_node('validate', validate_certificate_spec)
graph.add_node('print', printer_workflow)
graph.add_edge('validate', 'print')
graph.add_edge('print', END)
graph.set_entry_point('validate')
graph = graph.compile()
