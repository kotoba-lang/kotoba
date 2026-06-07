from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MotorState(TypedDict):
    spec_requirements: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: MotorState):
    specs = state.get('spec_requirements', {})
    logs = []
    compliant = True
    if specs.get('holding_torque_nm', 0) < 0.5:
        logs.append('Insufficient torque for industrial standard')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def assembly_routing(state: MotorState):
    return 'process' if state['is_compliant'] else END

def process_motor_workflow(state: MotorState):
    return {'validation_logs': state['validation_logs'] + ['Workflow: Motor assembly validated and cleared for production']}

graph = StateGraph(MotorState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_motor_workflow)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', assembly_routing)
graph.add_edge('process', END)
graph = graph.compile()
