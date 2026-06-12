from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class KeyCabinetState(TypedDict):
    spec_data: dict
    validation_results: List[str]

def validate_materials(state: KeyCabinetState):
    material = state.get('spec_data', {}).get('material', 'Steel')
    res = 'Valid' if material in ['Steel', 'Aluminum'] else 'Invalid: Substandard material'
    return {'validation_results': [res]}

def check_security_standard(state: KeyCabinetState):
    cert = state.get('spec_data', {}).get('security_cert', False)
    res = 'Certified' if cert else 'Warning: Security audit recommended'
    return {'validation_results': [res]}

graph = StateGraph(KeyCabinetState)
graph.add_node('material_check', validate_materials)
graph.add_node('security_check', check_security_standard)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'security_check')
graph.add_edge('security_check', END)
graph = graph.compile()
