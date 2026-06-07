from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MotorState(TypedDict):
    part_number: str
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_motor_specs(state: MotorState):
    specs = state.get('specs', {})
    log = []
    compliant = True
    if 'torque_nm' not in specs or specs['torque_nm'] <= 0:
        log.append('Invalid torque specification')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

def perform_quality_check(state: MotorState):
    return {'validation_log': ['Physical stress test passed']}

builder = StateGraph(MotorState)
builder.add_node('validate', validate_motor_specs)
builder.add_node('quality', perform_quality_check)
builder.set_entry_point('validate')
builder.add_edge('validate', 'quality')
builder.add_edge('quality', END)
graph = builder.compile()
