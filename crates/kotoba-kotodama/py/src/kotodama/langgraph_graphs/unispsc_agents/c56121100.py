from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtFurnishingState(TypedDict):
    spec_data: dict
    validation_log: list
    status: str

def validate_safety_standards(state: ArtFurnishingState):
    log = state.get('validation_log', [])
    specs = state.get('spec_data', {})
    if specs.get('material_safety') == 'compliant':
        log.append('Safety standards verified.')
    return {'validation_log': log, 'status': 'validated'}

workflow = StateGraph(ArtFurnishingState)
workflow.add_node('safety_check', validate_safety_standards)
workflow.set_entry_point('safety_check')
workflow.add_edge('safety_check', END)
graph = workflow.compile()
