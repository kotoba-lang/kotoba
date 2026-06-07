from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    serial_number: str
    compliance_checked: bool
    maintenance_required: bool

def validate_specs(state: ProcurementState):
    print('Validating industrial can opener power and safety ratings.')
    return {'compliance_checked': True}

def schedule_maintenance(state: ProcurementState):
    print('Scheduling preventative blade inspection and service interval.')
    return {'maintenance_required': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('schedule', schedule_maintenance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'schedule')
graph.add_edge('schedule', END)
graph = graph.compile()
