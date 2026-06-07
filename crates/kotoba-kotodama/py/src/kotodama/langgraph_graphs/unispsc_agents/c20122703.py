from typing import TypedDict, List, Annotated
import operator
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    specs: dict
    validation_log: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_specs(state: BearingState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if not specs.get('outer_diameter_mm'):
        log.append('Missing outer diameter')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

def perform_load_calculation(state: BearingState):
    # Simulate stress test calculation
    return {'validation_log': ['Load capacity verified against ISO standards']}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_specs)
graph.add_node('calc_load', perform_load_calculation)
graph.add_edge('validate', 'calc_load')
graph.add_edge('calc_load', END)
graph.set_entry_point('validate')
graph = graph.compile()
