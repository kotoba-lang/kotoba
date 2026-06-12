from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    part_specs: dict
    validation_passed: bool
    errors: List[str]

def validate_material(state: CastState):
    content = state.get('part_specs', {})
    if 'copper_content' in content and content['copper_content'] > 0.9:
        return {'validation_passed': True}
    return {'validation_passed': False, 'errors': ['Insufficient copper purity']}

def check_dimensions(state: CastState):
    # Simulate CAD validation logic
    return {'validation_passed': state.get('validation_passed', False)}

graph = StateGraph(CastState)
graph.add_node('material_check', validate_material)
graph.add_node('dim_check', check_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dim_check')
graph.add_edge('dim_check', END)
graph = graph.compile()
