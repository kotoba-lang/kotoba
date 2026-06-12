from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RawMaterialState(TypedDict):
    material_id: str
    purity_level: float
    compliance_checked: bool
    inspection_result: str

def validate_material(state: RawMaterialState) -> RawMaterialState:
    if state.get('purity_level', 0) >= 99.0:
        state['compliance_checked'] = True
        state['inspection_result'] = 'PASSED'
    else:
        state['compliance_checked'] = False
        state['inspection_result'] = 'FAILED_PURITY'
    return state

def check_inventory(state: RawMaterialState) -> RawMaterialState:
    print(f'Inventory check for {state.get('material_id')} complete.')
    return state

builder = StateGraph(RawMaterialState)
builder.add_node('validate', validate_material)
builder.add_node('inventory', check_inventory)
builder.add_edge('validate', 'inventory')
builder.add_edge('inventory', END)
builder.set_entry_point('validate')
graph = builder.compile()
