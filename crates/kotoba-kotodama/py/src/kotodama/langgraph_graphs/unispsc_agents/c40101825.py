from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class WaterHeaterState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: WaterHeaterState):
    specs = state.get('specs', {})
    log = []
    # Example validation: check for energy rating
    if 'energy_rating' not in specs:
        log.append('Missing mandatory field: energy_rating')
    is_valid = len(log) == 0
    return {'is_compliant': is_valid, 'validation_log': log}

def route_compliance(state: WaterHeaterState):
    return 'valid' if state['is_compliant'] else 'invalid'

graph = StateGraph(WaterHeaterState)
graph.add_node('validator', validate_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
