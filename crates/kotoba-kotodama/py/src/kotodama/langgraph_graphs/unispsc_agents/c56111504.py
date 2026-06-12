from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class OfficeFurnitureState(TypedDict):
    specifications: dict
    validation_status: bool
    compliance_report: str

def validate_furniture_specs(state: OfficeFurnitureState):
    specs = state.get('specifications', {})
    is_valid = 'BIFMA' in specs and 'dimensions' in specs
    return {'validation_status': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed'}

def finalize_procurement(state: OfficeFurnitureState):
    return {'compliance_report': 'Procurement order ready for review'}

graph = StateGraph(OfficeFurnitureState)
graph.add_node('validate', validate_furniture_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
