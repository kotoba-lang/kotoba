from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class PesticideState(TypedDict):
    product_id: str
    safety_clearance: bool
    hazard_level: int
    log: Annotated[list[str], operator.add]

def validate_product(state: PesticideState):
    level = state.get('hazard_level', 0)
    if level > 5:
        return {'safety_clearance': False, 'log': ['Hazard level too high for standard procurement']}
    return {'safety_clearance': True, 'log': ['Product safety validation passed']}

def storage_planning(state: PesticideState):
    if state.get('safety_clearance'):
        return {'log': ['Allocating secure hazardous material storage']}
    return {'log': ['Storage allocation rejected']}

graph = StateGraph(PesticideState)
graph.add_node('validate', validate_product)
graph.add_node('storage', storage_planning)
graph.add_edge('validate', 'storage')
graph.add_edge('storage', END)
graph.set_entry_point('validate')
graph = graph.compile()
