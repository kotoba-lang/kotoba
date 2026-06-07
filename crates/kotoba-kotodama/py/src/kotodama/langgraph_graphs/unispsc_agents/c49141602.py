from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WaterSportsState(TypedDict):
    product_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_material(state: WaterSportsState):
    specs = state.get('product_specs', {})
    if 'material' not in specs:
        return {'validation_passed': False, 'errors': ['Missing material specification']}
    return {'validation_passed': True}

def finalize_procurement(state: WaterSportsState):
    return {'validation_passed': True}

graph = StateGraph(WaterSportsState)
graph.add_node('validate_material', validate_material)
graph.add_node('finalize', finalize_procurement)
graph.add_edge('validate_material', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
