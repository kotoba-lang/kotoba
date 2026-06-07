from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RivetState(TypedDict):
    material_grade: str
    required_tensile: float
    inspection_passed: bool
    validation_logs: List[str]

def validate_material(state: RivetState):
    grade = state.get('material_grade', '')
    if grade in ['SUS304', 'SUS316', 'Grade 8']:
        return {'validation_logs': ['Material validated']}
    return {'validation_logs': ['Invalid material grade']}

def check_load_bearing(state: RivetState):
    if state.get('required_tensile', 0) > 500.0:
        return {'inspection_passed': False, 'validation_logs': ['Tensile test failed']}
    return {'inspection_passed': True, 'validation_logs': ['Tensile test passed']}

graph = StateGraph(RivetState)
graph.add_node('material', validate_material)
graph.add_node('load', check_load_bearing)
graph.set_entry_point('material')
graph.add_edge('material', 'load')
graph.add_edge('load', END)
graph = graph.compile()
