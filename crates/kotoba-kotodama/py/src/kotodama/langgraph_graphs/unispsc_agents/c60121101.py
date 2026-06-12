from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrawingPaperState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_logs: list

def validate_paper_specs(state: DrawingPaperState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('gsm', 0) < 60: errors.append('GSM below standard weight')
    if not specs.get('is_acid_free', True): errors.append('Must be acid-free')
    return {'validation_passed': len(errors) == 0, 'error_logs': errors}

workflow = StateGraph(DrawingPaperState)
workflow.add_node('validation', validate_paper_specs)
workflow.set_entry_point('validation')
workflow.add_edge('validation', END)
graph = workflow.compile()
