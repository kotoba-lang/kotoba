from typing import TypedDict
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material_type: str
    is_anti_static: bool
    validation_status: str

def validate_spec(state: PackagingState):
    if state.get('material_type') == 'polyethylene':
        return {'validation_status': 'PASS'}
    return {'validation_status': 'FAIL'}

def process_procurement(state: PackagingState):
    print(f'Processing procurement with status: {state.get('validation_status')}')
    return state

builder = StateGraph(PackagingState)
builder.add_node('validate', validate_spec)
builder.add_node('process', process_procurement)
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
builder.set_entry_point('validate')
graph = builder.compile()
