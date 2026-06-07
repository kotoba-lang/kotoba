from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SensorProcurementState(TypedDict):
    specs: dict
    validation_results: list[str]
    is_approved: bool

def validate_sensor_specs(state: SensorProcurementState):
    specs = state.get('specs', {})
    results = []
    if specs.get('response_time_ms', 0) > 50:
        results.append('Response time exceeds industrial safety threshold')
    if not specs.get('ingress_protection_rating', '').startswith('IP6'):
        results.append('Insufficient IP rating for factory environment')
    return {'validation_results': results, 'is_approved': len(results) == 0}

def finalize_order(state: SensorProcurementState):
    return {'validation_results': state.get('validation_results', []) + ['Order routed to procurement']}

graph = StateGraph(SensorProcurementState)
graph.add_node('validate', validate_sensor_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
