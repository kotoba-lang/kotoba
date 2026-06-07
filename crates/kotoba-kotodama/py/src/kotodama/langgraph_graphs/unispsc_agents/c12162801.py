from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AdhesivesState(TypedDict):
    procurement_id: str
    material_specs: dict
    compliance_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_chemical_safety(state: AdhesivesState) -> AdhesivesState:
    specs = state.get('material_specs', {})
    if 'msds_data' in specs and 'toxicity_level' in specs:
        return {'compliance_checks': ['Chemical Safety Validated']}
    return {'compliance_checks': ['Safety Check Failed']}

def perform_durability_analysis(state: AdhesivesState) -> AdhesivesState:
    return {'compliance_checks': ['Durability Standards Met']}

graph = StateGraph(AdhesivesState)
graph.add_node('safety_check', validate_chemical_safety)
graph.add_node('durability_analysis', perform_durability_analysis)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'durability_analysis')
graph.add_edge('durability_analysis', END)
graph = graph.compile()
