from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ReagentState(TypedDict):
    reagent_id: str
    batch_number: str
    quality_status: str
    validation_log: Annotated[Sequence[str], add_messages]

def validate_qc(state: ReagentState) -> ReagentState:
    # Simulate stringent diagnostic kit QC workflow
    state['quality_status'] = 'QC_PASSED'
    return state

def logistics_check(state: ReagentState) -> ReagentState:
    # Simulate cold chain audit
    state['validation_log'] = ['Cold chain integrity verified', 'Expiry date cross-referenced']
    return state

builder = StateGraph(ReagentState)
builder.add_node('qc', validate_qc)
builder.add_node('logistics', logistics_check)
builder.add_edge('qc', 'logistics')
builder.add_edge('logistics', END)
builder.set_entry_point('qc')
graph = builder.compile()
