from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class SiliconMaterialState(TypedDict):
    purity_check_passed: bool
    particle_analysis: List[float]
    compliance_validated: bool

def validate_purity(state: SiliconMaterialState):
    # Simulate spectroscopic purity validation
    return {'purity_check_passed': True}

def inspect_surface(state: SiliconMaterialState):
    # Simulate atomic force microscopy analysis
    return {'particle_analysis': [0.01, 0.02, 0.01]}

def check_compliance(state: SiliconMaterialState):
    # Dual-use export control check
    return {'compliance_validated': True}

graph = StateGraph(SiliconMaterialState)
graph.add_node('purity', validate_purity)
graph.add_node('surface', inspect_surface)
graph.add_node('compliance', check_compliance)
graph.add_edge('purity', 'surface')
graph.add_edge('surface', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('purity')
graph = graph.compile()
