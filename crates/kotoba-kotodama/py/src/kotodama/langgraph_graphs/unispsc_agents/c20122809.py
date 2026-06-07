from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    part_number: str
    specifications: dict
    validation_log: List[str]
    is_compliant: bool

def validate_specs(state: ActuatorState):
    specs = state.get('specifications', {})
    log = []
    compliant = True
    if specs.get('peak_torque_nm', 0) < 1.0:
        log.append('Torque insufficient for industrial use')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

def route_to_testing(state: ActuatorState):
    return 'test' if state['is_compliant'] else END

builder = StateGraph(ActuatorState)
builder.add_node('validate', validate_specs)
builder.add_edge('validate', END)
builder.set_entry_point('validate')
graph = builder.compile()
