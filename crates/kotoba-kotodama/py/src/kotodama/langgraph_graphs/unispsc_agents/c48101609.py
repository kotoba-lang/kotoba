from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PastaMachineState(TypedDict):
    spec_requirements: dict
    validation_log: List[str]
    is_compliant: bool

def validate_food_safety(state: PastaMachineState):
    log = state.get('validation_log', [])
    specs = state.get('spec_requirements', {})
    compliant = specs.get('food_grade') == True
    log.append('Food safety validation complete')
    return {'validation_log': log, 'is_compliant': compliant}

def validate_power_specs(state: PastaMachineState):
    log = state.get('validation_log', [])
    specs = state.get('spec_requirements', {})
    if 'voltage' in specs:
        log.append(f'Voltage validated: {specs["voltage"]}')
    return {'validation_log': log}

graph = StateGraph(PastaMachineState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('power_check', validate_power_specs)
graph.add_edge('safety_check', 'power_check')
graph.add_edge('power_check', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
