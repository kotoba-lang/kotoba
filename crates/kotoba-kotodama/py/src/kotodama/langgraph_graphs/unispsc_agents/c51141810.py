from typing import TypedDict
from langgraph.graph import StateGraph, END

class ZopicloneState(TypedDict):
    batch_id: str
    compliance_checked: bool
    qc_passed: bool

def validate_compliance(state: ZopicloneState):
    print(f'Checking compliance for batch {state.get(batch_id)}...')
    return {'compliance_checked': True}

def run_qc(state: ZopicloneState):
    print('Executing pharmaceutical QC protocols...')
    return {'qc_passed': True}

graph = StateGraph(ZopicloneState)
graph.add_node('compliance', validate_compliance)
graph.add_node('qc', run_qc)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'qc')
graph.add_edge('qc', END)
graph = graph.compile()
