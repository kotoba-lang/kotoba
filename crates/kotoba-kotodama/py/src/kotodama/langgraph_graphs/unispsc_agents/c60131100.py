from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class InstrumentState(TypedDict):
    instrument_type: str
    quality_grade: str
    validation_passed: bool

def validate_instrument(state: InstrumentState):
    # Business logic for confirming brass instrument specifications
    is_valid = state.get('quality_grade') in ['Pro', 'Intermediate']
    return {'validation_passed': is_valid}

def approval_step(state: InstrumentState):
    return {'validation_passed': True}

graph = StateGraph(InstrumentState)
graph.add_node('validate', validate_instrument)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
