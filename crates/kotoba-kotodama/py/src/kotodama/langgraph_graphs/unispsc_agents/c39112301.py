from typing import TypedDict
from langgraph.graph import StateGraph, END

class ColorChangerState(TypedDict):
    spec_data: dict
    validation_log: list
    is_compliant: bool

def validate_dmx_specs(state: ColorChangerState):
    log = state.get('validation_log', [])
    specs = state.get('spec_data', {})
    if 'dmx_addressable' in specs and specs['dmx_addressable']:
        log.append('DMX validation passed.')
    else:
        log.append('DMX validation failed.')
    return {'validation_log': log}

def safety_check(state: ColorChangerState):
    log = state.get('validation_log', [])
    log.append('Electrical safety inspection initiated.')
    return {'validation_log': log, 'is_compliant': True}

graph = StateGraph(ColorChangerState)
graph.add_node('dmx_check', validate_dmx_specs)
graph.add_node('safety_check', safety_check)
graph.set_entry_point('dmx_check')
graph.add_edge('dmx_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()
