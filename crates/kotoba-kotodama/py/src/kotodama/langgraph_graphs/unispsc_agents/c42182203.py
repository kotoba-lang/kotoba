from typing import TypedDict
from langgraph.graph import StateGraph, END
class ThermometerCaseState(TypedDict):
    case_type: str
    material: str
    is_sterile: bool
    validation_stage: str
def validate_material(state: ThermometerCaseState):
    print(f'Validating material: {state.get(material)}')
    return {'validation_stage': 'material_check_passed'}
def check_sterility(state: ThermometerCaseState):
    if state.get('is_sterile'):
        return {'validation_stage': 'sterility_verified'}
    return {'validation_stage': 'manual_inspection_required'}
graph = StateGraph(ThermometerCaseState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_sterility', check_sterility)
graph.add_edge('validate_material', 'check_sterility')
graph.add_edge('check_sterility', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
