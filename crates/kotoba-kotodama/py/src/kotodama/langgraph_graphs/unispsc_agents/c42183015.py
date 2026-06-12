from typing import TypedDict
from langgraph.graph import StateGraph, END

class SlitLampState(TypedDict):
    spec_data: dict
    validation_results: list

def validate_optics(state: SlitLampState):
    print('Validating optical resolution and calibration.')
    return {'validation_results': ['Optics OK']}

def check_compliance(state: SlitLampState):
    print('Verifying medical device registration.')
    return {'validation_results': state['validation_results'] + ['Compliance OK']}

graph = StateGraph(SlitLampState)
graph.add_node('optics', validate_optics)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('optics')
graph.add_edge('optics', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
