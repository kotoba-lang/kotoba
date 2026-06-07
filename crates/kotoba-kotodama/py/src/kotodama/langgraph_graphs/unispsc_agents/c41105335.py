from typing import TypedDict
from langgraph.graph import StateGraph, END

class DNAWorkflowState(TypedDict):
    purity_check: bool
    temp_log_verified: bool
    is_compliant: bool

def validate_quality(state: DNAWorkflowState):
    # Simulate QC logic for DNA markers
    return {'is_compliant': state.get('purity_check', False) and state.get('temp_log_verified', False)}

graph = StateGraph(DNAWorkflowState)
graph.add_node('qc_validation', validate_quality)
graph.set_entry_point('qc_validation')
graph.add_edge('qc_validation', END)
graph = graph.compile()
