from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ServoState(TypedDict):
    specs: dict
    validation_results: Annotated[list, operator.add]
    status: str

def validate_servo_specs(state: ServoState):
    specs = state.get('specs', {})
    results = []
    if specs.get('torque', 0) < 0.5:
        results.append('Error: Insufficient torque for industrial application')
    return {'validation_results': results, 'status': 'VALIDATED' if not results else 'FAILED'}

def compile_robotics_graph():
    workflow = StateGraph(ServoState)
    workflow.add_node('validate', validate_servo_specs)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', END)
    return workflow.compile()

graph = compile_robotics_graph()
