from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CameraComponentState(TypedDict):
    spec_sheet_url: str
    validation_passed: bool
    compliance_tags: List[str]

def validate_camera_block(state: CameraComponentState):
    # Simulate CAD validation logic
    return {'validation_passed': True, 'compliance_tags': ['ISO-9001']}

def check_export_control(state: CameraComponentState):
    # Simulate dual-use check for high-precision components
    return {'compliance_tags': state['compliance_tags'] + ['export-screened']}

graph = StateGraph(CameraComponentState)
graph.add_node('validate', validate_camera_block)
graph.add_node('export_check', check_export_control)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
