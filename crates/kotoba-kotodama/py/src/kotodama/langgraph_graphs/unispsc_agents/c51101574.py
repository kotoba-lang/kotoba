from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    quality_checks: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_batch(state: ReagentState) -> ReagentState:
    print(f'Validating batch: {state[reagent_id]}')
    return {quality_checks: ['ISO_13485_VERIFIED', 'TEMP_CONTROL_PASSED'], is_approved: True}

def process_reagent(state: ReagentState) -> ReagentState:
    return {is_approved: True}

builder = StateGraph(ReagentState)
builder.add_node('validate', validate_batch)
builder.add_node('process', process_reagent)
builder.set_entry_point('validate')
builder.add_edge('validate', 'process')
builder.add_edge('process', END)
graph = builder.compile()
