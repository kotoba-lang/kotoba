from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CopyPaperState(TypedDict):
    spec_requirements: dict
    validation_results: List[str]
    is_compliant: bool

def validate_paper_spec(state: CopyPaperState):
    specs = state.get('spec_requirements', {})
    results = []
    if specs.get('basis_weight_gsm', 0) < 60:
        results.append('Basis weight below industry standard 60gsm.')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def printer_check(state: CopyPaperState):
    print('Running printer compatibility simulation...')
    return {'validation_results': state['validation_results'] + ['Printer test passed']}

graph = StateGraph(CopyPaperState)
graph.add_node('validate', validate_paper_spec)
graph.add_node('printer_check', printer_check)
graph.add_edge('validate', 'printer_check')
graph.add_edge('printer_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
