from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AddressingMachineState(TypedDict):
    model_id: str
    specs: dict
    is_validated: bool

def validate_specs(state: AddressingMachineState):
    print(f'Validating specs for model {state.get('model_id')}')
    return {'is_validated': True}

def route_procurement(state: AddressingMachineState):
    return 'end'

graph = StateGraph(AddressingMachineState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
