from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item_name: str
    material: str
    is_food_grade: bool
    validation_errors: List[str]

def validate_material(state: ProcurementState):
    errors = []
    if not state.get('material'):
        errors.append('Material specification missing')
    if not state.get('is_food_grade'):
        errors.append('Item must be food grade certified')
    return {'validation_errors': errors}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
