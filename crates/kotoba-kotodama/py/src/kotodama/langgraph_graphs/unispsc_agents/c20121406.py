from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    part_number: str
    spec_data: dict
    validation_log: List[str]
    is_approved: bool

def validate_specs(state: ServoState):
    log = state.get('validation_log', [])
    specs = state.get('spec_data', {})
    if specs.get('torque_rating_nm', 0) > 0:
        log.append('Torque validated.')
    return {'validation_log': log, 'is_approved': True}

def process_integration(state: ServoState):
    return {'validation_log': state.get('validation_log', []) + ['Integration logic processed.']}

graph = StateGraph(ServoState)
graph.add_node('validate', validate_specs)
graph.add_node('integrate', process_integration)
graph.add_edge('validate', 'integrate')
graph.add_edge('integrate', END)
graph.set_entry_point('validate')
graph = graph.compile()
