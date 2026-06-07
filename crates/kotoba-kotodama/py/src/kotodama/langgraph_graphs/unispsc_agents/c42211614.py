from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    specification: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: ProcurementState):
    log = []
    compliant = True
    specs = state.get('specification', {})
    if specs.get('weight_capacity_kg', 0) < 150:
        log.append('Weight capacity below standard requirement')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
