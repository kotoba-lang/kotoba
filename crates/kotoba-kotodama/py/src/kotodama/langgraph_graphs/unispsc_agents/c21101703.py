from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AgriculturalMachineState(TypedDict):
    equipment_id: str
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: AgriculturalMachineState):
    log = []
    compliant = True
    if state['specs'].get('load_capacity', 0) <= 0:
        log.append('Invalid load capacity')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def route_by_compliance(state: AgriculturalMachineState):
    return 'process' if state['is_compliant'] else 'manual_review'

graph = StateGraph(AgriculturalMachineState)
graph.add_node('validation', validate_specs)
graph.add_edge('validation', 'manual_review')
graph.set_entry_point('validation')

graph = graph.compile()
