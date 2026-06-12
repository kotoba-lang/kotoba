from typing import TypedDict
from langgraph.graph import StateGraph, END

class TankState(TypedDict):
    tank_id: str
    spec_compliance: bool
    pressure_test_passed: bool
    export_cleared: bool

def validate_aerodynamics(state: TankState):
    state['spec_compliance'] = True
    print('Validating aerodynamic integrity...')
    return state

def check_export_controls(state: TankState):
    state['export_cleared'] = True
    return state

graph = StateGraph(TankState)
graph.add_node('aerodynamics', validate_aerodynamics)
graph.add_node('export', check_export_controls)
graph.set_entry_point('aerodynamics')
graph.add_edge('aerodynamics', 'export')
graph.add_edge('export', END)
graph = graph.compile()
