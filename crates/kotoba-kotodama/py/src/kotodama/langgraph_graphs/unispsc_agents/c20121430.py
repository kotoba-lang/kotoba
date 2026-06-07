from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec_data: dict
    validation_log: list[str]
    is_compliant: bool

def validate_effector_specs(state: RobotState):
    specs = state.get('spec_data', {})
    logs = []
    compliant = True
    if specs.get('load_capacity_kg', 0) <= 0:
        logs.append('Invalid load capacity')
        compliant = False
    return {'validation_log': logs, 'is_compliant': compliant}

def process_procurement(state: RobotState):
    if state['is_compliant']:
        return {'validation_log': state['validation_log'] + ['Procurement approved']}
    return {'validation_log': state['validation_log'] + ['Procurement rejected']}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_effector_specs)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()
