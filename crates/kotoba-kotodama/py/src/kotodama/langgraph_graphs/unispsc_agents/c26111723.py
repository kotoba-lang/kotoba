from typing import TypedDict
from langgraph.graph import StateGraph, END

class BatteryCabinetState(TypedDict):
    specs: dict
    validation_results: list
    is_compliant: bool

def validate_enclosure_specs(state: BatteryCabinetState):
    specs = state.get('specs', {})
    results = []
    if specs.get('fire_rating') != 'UL94-V0':
        results.append('Fire resistance below required standard')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: BatteryCabinetState):
    return 'approved' if state['is_compliant'] else 'flag_for_review'

graph = StateGraph(BatteryCabinetState)
graph.add_node('validate', validate_enclosure_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
