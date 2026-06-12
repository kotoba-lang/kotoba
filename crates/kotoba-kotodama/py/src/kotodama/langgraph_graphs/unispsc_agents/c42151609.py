from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalMatState(TypedDict):
    material_info: str
    is_autoclavable: bool
    validation_status: str

def validate_material(state: DentalMatState):
    print('Validating material safety protocol...')
    status = 'PASS' if state.get('material_info') == 'Silicone' else 'FAIL'
    return {'validation_status': status}

def check_sterilization(state: DentalMatState):
    print('Verifying sterilization requirements...')
    return {'is_autoclavable': True}

graph = StateGraph(DentalMatState)
graph.add_node('validate', validate_material)
graph.add_node('sterility', check_sterilization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
