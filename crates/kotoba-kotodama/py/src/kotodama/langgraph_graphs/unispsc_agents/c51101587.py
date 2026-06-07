from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ReagentState(TypedDict):
    batch_id: str
    quality_logs: Annotated[List[str], operator.add]
    is_validated: bool

def validate_cold_chain(state: ReagentState):
    state['quality_logs'].append('Verifying cold chain logs...')
    return {'is_validated': True}

def perform_assay_qc(state: ReagentState):
    state['quality_logs'].append('Checking assay sensitivity metrics...')
    return {'is_validated': True}

graph = StateGraph(ReagentState)
graph.add_node('cold_chain', validate_cold_chain)
graph.add_node('assay_qc', perform_assay_qc)
graph.set_entry_point('cold_chain')
graph.add_edge('cold_chain', 'assay_qc')
graph.add_edge('assay_qc', END)
graph = graph.compile()
