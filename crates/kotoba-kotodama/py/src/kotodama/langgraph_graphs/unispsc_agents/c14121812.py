from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class PackagingState(TypedDict):
    material_type: str
    spec_data: dict
    validation_results: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_spec(state: PackagingState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('tensile_strength', 0) < 30:
        results.append('Low tensile strength detected')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def process_packaging(state: PackagingState):
    return {'validation_results': ['Material check complete']}

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_spec)
graph.add_node('process', process_packaging)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
