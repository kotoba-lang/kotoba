from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtractionState(TypedDict):
    device_id: str
    is_sterile: bool
    passed_qc: bool

def validate_sterility(state: ExtractionState):
    return {'is_sterile': True} if state.get('device_id') else {'is_sterile': False}

def conduct_quality_audit(state: ExtractionState):
    return {'passed_qc': state['is_sterile']}

graph = StateGraph(ExtractionState)
graph.add_node('check_sterility', validate_sterility)
graph.add_node('qc_audit', conduct_quality_audit)
graph.set_entry_point('check_sterility')
graph.add_edge('check_sterility', 'qc_audit')
graph.add_edge('qc_audit', END)
graph = graph.compile()
