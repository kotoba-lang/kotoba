from typing import TypedDict
from langgraph.graph import StateGraph, END

class MonotypeState(TypedDict):
    serial_number: str
    spec_verified: bool
    maintenance_plan_confirmed: bool

def validate_specs(state: MonotypeState):
    state['spec_verified'] = True
    print('Validating machine precision specs...')
    return state

def check_maintenance(state: MonotypeState):
    state['maintenance_plan_confirmed'] = True
    return state

graph = StateGraph(MonotypeState)
graph.add_node('validate', validate_specs)
graph.add_node('maintenance', check_maintenance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'maintenance')
graph.add_edge('maintenance', END)
graph = graph.compile()
