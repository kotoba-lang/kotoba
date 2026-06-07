from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PipeSpecState(TypedDict):
    material_grade: str
    dimensions: dict
    is_compliant: bool
    validation_log: List[str]

def validate_materials(state: PipeSpecState):
    grade = state.get('material_grade')
    valid = grade in ['6061-T6', '6063-T5', '5052-H32']
    return {'is_compliant': valid, 'validation_log': [f'Material check: {valid}']}

def validate_geometry(state: PipeSpecState):
    dims = state.get('dimensions', {})
    valid = dims.get('thickness', 0) > 2.0
    return {'is_compliant': state['is_compliant'] and valid, 'validation_log': state['validation_log'] + [f'Geometry check: {valid}']}

graph = StateGraph(PipeSpecState)
graph.add_node('material_check', validate_materials)
graph.add_node('geometry_check', validate_geometry)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'geometry_check')
graph.add_edge('geometry_check', END)
graph = graph.compile()
