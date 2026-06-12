from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CerclageProcurementState(TypedDict):
    instrument_id: str
    compliance_docs: List[str]
    status: str

def validate_certification(state: CerclageProcurementState):
    docs = state.get('compliance_docs', [])
    if 'ISO_13485' in docs:
        return {'status': 'CERTIFIED'}
    return {'status': 'REJECTED'}

def finalize_process(state: CerclageProcurementState):
    return {'status': 'READY_FOR_PROCUREMENT'}

graph = StateGraph(CerclageProcurementState)
graph.add_node('validate', validate_certification)
graph.add_node('finalize', finalize_process)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
