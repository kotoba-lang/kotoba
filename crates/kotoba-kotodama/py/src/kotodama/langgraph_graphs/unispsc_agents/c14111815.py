from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class TapeDispenserState(TypedDict):
    spec_requirements: dict
    validation_logs: List[str]
    is_approved: bool

def validate_dispenser_spec(state: TapeDispenserState) -> TapeDispenserState:
    specs = state.get('spec_requirements', {})
    width = specs.get('width', 0)
    logs = state.get('validation_logs', [])
    if 10 <= width <= 50:
        logs.append('Spec validated: Width compatible')
        return {'validation_logs': logs, 'is_approved': True}
    else:
        logs.append('Spec error: Width out of range')
        return {'validation_logs': logs, 'is_approved': False}

def process_procurement(state: TapeDispenserState) -> TapeDispenserState:
    if state.get('is_approved'):
        state['validation_logs'].append('Procurement workflow initiated')
    return state

builder = StateGraph(TapeDispenserState)
builder.add_node('validate', validate_dispenser_spec)
builder.add_node('procure', process_procurement)
builder.set_entry_point('validate')
builder.add_edge('validate', 'procure')
builder.add_edge('procure', END)
graph = builder.compile()
