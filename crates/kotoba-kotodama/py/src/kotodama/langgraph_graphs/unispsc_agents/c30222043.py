from typing import TypedDict
from langgraph.graph import StateGraph, END

class CrossroadState(TypedDict):
    spec_data: dict
    validation_result: bool

def validate_infrastructure(state: CrossroadState):
    specs = state.get('spec_data', {})
    is_valid = 'regulatory_compliance_certificate' in specs and 'load_bearing_capacity' in specs
    return {'validation_result': is_valid}

def process_procurement(state: CrossroadState):
    print('Processing procurement workflow for crossroad infrastructure...')
    return state

graph = StateGraph(CrossroadState)
graph.add_node('validate', validate_infrastructure)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
