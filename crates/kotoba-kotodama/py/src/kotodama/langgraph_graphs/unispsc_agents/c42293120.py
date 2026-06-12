from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalDeviceState(TypedDict):
    device_id: str
    specifications: dict
    is_compliant: bool
    validation_log: List[str]

def validate_medical_grade(state: SurgicalDeviceState):
    log = state.get('validation_log', [])
    specs = state.get('specifications', {})
    # Check for surgical grade steel
    is_compliant = specs.get('material') == '316L Stainless Steel'
    log.append(f'Material validation: {is_compliant}')
    return {'is_compliant': is_compliant, 'validation_log': log}

def check_certification(state: SurgicalDeviceState):
    is_compliant = state.get('is_compliant', False)
    if is_compliant:
        # Verify ISO 13485
        is_compliant = state.get('specifications', {}).get('iso_cert', False)
    return {'is_compliant': is_compliant}

graph = StateGraph(SurgicalDeviceState)
graph.add_node('MaterialCheck', validate_medical_grade)
graph.add_node('CertCheck', check_certification)
graph.set_entry_point('MaterialCheck')
graph.add_edge('MaterialCheck', 'CertCheck')
graph.add_edge('CertCheck', END)
graph = graph.compile()
