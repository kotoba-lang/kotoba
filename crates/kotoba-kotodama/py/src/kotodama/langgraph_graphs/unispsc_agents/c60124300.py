from typing import TypedDict
from langgraph.graph import StateGraph, END

class CeramicsProcurementState(TypedDict):
    item_name: str
    specs: dict
    approved: bool

def validate_equipment_specs(state: CeramicsProcurementState):
    # Business logic for kiln/wheel validation
    print(f'Validating: {state[item_name]}')
    return {'approved': True}

graph = StateGraph(CeramicsProcurementState)
graph.add_node('validate', validate_equipment_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
