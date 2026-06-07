from typing import TypedDict
from langgraph.graph import StateGraph, END

class CDState(TypedDict):
    quantity: int
    capacity: int
    is_printable: bool
    validation_status: str

def validate_specs(state: CDState):
    print(f'Validating CD specs: {state.get("capacity")}MB capacity.')
    return {'validation_status': 'PASSED'}

def update_inventory(state: CDState):
    print('Updating procurement database with verified media.')
    return {'validation_status': 'INVENTORY_UPDATED'}

graph = StateGraph(CDState)
graph.add_node('validate', validate_specs)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()
