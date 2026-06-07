from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoinMachineState(TypedDict):
    model_number: str
    validation_passed: bool
    maintenance_required: bool

def validate_machine(state: CoinMachineState):
    # Simulate CAD/Spec validation for coin wrapper
    state['validation_passed'] = bool(state.get('model_number'))
    return state

def check_maintenance(state: CoinMachineState):
    state['maintenance_required'] = True
    return state

graph = StateGraph(CoinMachineState)
graph.add_node('validate', validate_machine)
graph.add_node('maintenance', check_maintenance)
graph.add_edge('validate', 'maintenance')
graph.add_edge('maintenance', END)
graph.set_entry_point('validate')
graph = graph.compile()
