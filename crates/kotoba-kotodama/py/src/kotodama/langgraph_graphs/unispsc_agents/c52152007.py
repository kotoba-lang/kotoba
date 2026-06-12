from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class KitchenwareState(TypedDict):
    spec_data: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_material(state: KitchenwareState):
    material = state.get('spec_data', {}).get('material')
    results = ['Material verified' if material in ['ceramic', 'glass', 'stainless_steel'] else 'Material check failed']
    return {'validation_results': results}

def check_compliance(state: KitchenwareState):
    compliant = 'Material check failed' not in state['validation_results']
    return {'is_compliant': compliant}

graph = StateGraph(KitchenwareState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
