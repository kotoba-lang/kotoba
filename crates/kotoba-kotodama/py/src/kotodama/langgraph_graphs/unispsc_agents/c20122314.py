from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class SensorState(TypedDict):
    sensor_id: str
    specs: dict
    validation_passed: bool
    log: Annotated[List[str], add_messages]

def validate_specs(state: SensorState):
    specs = state.get('specs', {})
    # Logic: Verify minimum IP67 for industrial use
    ip_rating = specs.get('ingress_protection_rating', 0)
    passed = ip_rating >= 67
    return {'validation_passed': passed, 'log': [f'Validation: {passed}']}

def route_by_spec(state: SensorState):
    return 'process' if state['validation_passed'] else END

builder = StateGraph(SensorState)
builder.add_node('validate', validate_specs)
builder.add_node('process', lambda state: {'log': ['Processing sensor compliance...']})
builder.set_entry_point('validate')
builder.add_conditional_edges('validate', route_by_spec)
builder.add_edge('process', END)
graph = builder.compile()
