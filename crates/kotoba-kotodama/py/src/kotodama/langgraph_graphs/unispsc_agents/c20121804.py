from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SensorState(TypedDict):
    sensor_id: str
    specifications: dict
    validation_results: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_sensor_specs(state: SensorState):
    specs = state.get('specifications', {})
    results = []
    if specs.get('ip_rating', 0) < 65:
        results.append('Insufficient IP rating for industrial environment')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_to_testing(state: SensorState):
    return 'testing' if state['is_compliant'] else 'reject'

builder = StateGraph(SensorState)
builder.add_node('validate', validate_sensor_specs)
builder.add_edge('validate', END)
builder.set_entry_point('validate')
graph = builder.compile()
