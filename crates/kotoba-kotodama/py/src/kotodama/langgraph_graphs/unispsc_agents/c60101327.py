from typing import TypedDict
from langgraph.graph import StateGraph, END

class FlashCardState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: FlashCardState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('paper_gsm', 0) < 200:
        errors.append('Card weight too low for durability')
    return {'validation_passed': len(errors) == 0, 'error_log': errors}

def process_procurement(state: FlashCardState):
    print('Processing flash card procurement requirements...')
    return {}

graph = StateGraph(FlashCardState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
