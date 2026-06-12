from typing import TypedDict
from langgraph.graph import StateGraph, END

class MemoryBookState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_materials(state: MemoryBookState):
    """Validates if the memory book specs meet archival standards."""
    specs = state.get('spec_data', {})
    is_acid_free = specs.get('paper_acid_free') is True
    return {"validation_passed": is_acid_free}

def process_finalization(state: MemoryBookState):
    print('Finalizing memory book procurement order.')
    return state

builder = StateGraph(MemoryBookState)
builder.add_node('validate', validate_materials)
builder.add_node('finalize', process_finalization)
builder.set_entry_point('validate')
builder.add_edge('validate', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()
