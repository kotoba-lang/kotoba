from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RCNetsState(TypedDict):
    specs: dict
    validation_results: List[str]
    is_compliant: bool

def validate_specs(state: RCNetsState):
    specs = state.get('specs', {})
    results = []
    if 'resistance_ohms' not in specs: results.append('Missing resistance')
    if 'capacitance_farads' not in specs: results.append('Missing capacitance')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

workflow = StateGraph(RCNetsState)
workflow.add_node('validate', validate_specs)
workflow.set_entry_point('validate')
workflow.add_edge('validate', END)
graph = workflow.compile()
