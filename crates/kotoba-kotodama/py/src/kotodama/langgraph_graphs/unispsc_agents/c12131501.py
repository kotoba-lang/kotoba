from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MaterialIngestState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    log: Annotated[List[str], operator.add]

def validate_material(state: MaterialIngestState):
    # Simulate high-purity validation logic
    is_pure = True
    return {'purity_check': is_pure, 'log': ['Purity validation passed']}

def perform_safety_check(state: MaterialIngestState):
    # Simulate hazardous material regulatory check
    is_safe = True
    return {'safety_clearance': is_safe, 'log': ['Safety clearance successful']}

graph = StateGraph(MaterialIngestState)
graph.add_node('validate', validate_material)
graph.add_node('safety', perform_safety_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
