from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GripperState(TypedDict):
    part_id: str
    specs: dict
    validation_log: List[str]
    approved: bool

def validate_specs(state: GripperState):
    log = state.get('validation_log', [])
    specs = state.get('specs', {})
    if specs.get('repeatability_microns', 100) < 50:
        log.append('High precision validated')
    return {'validation_log': log}

def check_compliance(state: GripperState):
    log = state.get('validation_log', [])
    if 'material_certification' in state.get('specs', {}):
        log.append('Compliance passed')
        return {'validation_log': log, 'approved': True}
    return {'validation_log': log, 'approved': False}

graph = StateGraph(GripperState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
