from typing import TypedDict
from langgraph.graph import StateGraph, END

class WheelClampState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_clamp_specs(state: WheelClampState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if specs.get('material') != 'hardened_steel':
        compliant = False
        log.append('Material must be hardened steel.')
    return {'is_compliant': compliant, 'validation_log': log}

graph = StateGraph(WheelClampState)
graph.add_node('validate', validate_clamp_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
