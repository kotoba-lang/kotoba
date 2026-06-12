from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_technical_specs(state: ProcessingState):
    specs = state.get('spec_data', {})
    results = []
    if 'operating_temp' in specs and specs['operating_temp'] > 1200:
        results.append('High-temp compliance check required.')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: ProcessingState):
    return 'compliant' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_technical_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
