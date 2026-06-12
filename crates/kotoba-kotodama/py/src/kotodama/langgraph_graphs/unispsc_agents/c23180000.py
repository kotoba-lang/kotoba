from typing import TypedDict
from langgraph.graph import StateGraph, END

class MachineState(TypedDict):
    equipment_id: str
    compliance_checked: bool
    maintenance_plan: str

def validate_specs(state: MachineState) -> MachineState:
    # Simulate CAD/Spec validation for industrial machinery
    state['compliance_checked'] = True
    return state

def create_plan(state: MachineState) -> MachineState:
    state['maintenance_plan'] = 'Preventive maintenance scheduled quarterly'
    return state

graph = StateGraph(MachineState)
graph.add_node('validate', validate_specs)
graph.add_node('plan', create_plan)
graph.set_entry_point('validate')
graph.add_edge('validate', 'plan')
graph.add_edge('plan', END)
graph = graph.compile()
