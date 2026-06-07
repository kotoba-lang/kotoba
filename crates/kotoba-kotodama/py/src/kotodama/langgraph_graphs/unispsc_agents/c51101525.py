from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ReagentState(TypedDict):
    reagent_id: str
    quality_checks: Annotated[Sequence[str], operator.add]
    status: str

def validate_cold_chain(state: ReagentState):
    # Simulate cold chain validation logic
    return {'quality_checks': ['Cold chain verified: passed']}

def perform_batch_qc(state: ReagentState):
    # Simulate QC process
    return {'quality_checks': ['Batch QC: verified'], 'status': 'READY_FOR_DISTRIBUTION'}

graph = StateGraph(ReagentState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('perform_batch_qc', perform_batch_qc)
graph.set_entry_point('validate_cold_chain')
graph.add_edge('validate_cold_chain', 'perform_batch_qc')
graph.add_edge('perform_batch_qc', END)

graph = graph.compile()
