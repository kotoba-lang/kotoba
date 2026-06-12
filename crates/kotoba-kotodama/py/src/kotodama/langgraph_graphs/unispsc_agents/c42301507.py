from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class VideoContentState(TypedDict):
    content_metadata: dict
    review_status: str
    compliance_tags: List[str]

def validate_medical_accuracy(state: VideoContentState):
    state['review_status'] = 'Pending_Peer_Review'
    return state

def check_regulatory_compliance(state: VideoContentState):
    state['compliance_tags'] = ['Clinical_Accuracy', 'Patient_Privacy_Aware']
    return state

graph = StateGraph(VideoContentState)
graph.add_node('validate_accuracy', validate_medical_accuracy)
graph.add_node('check_compliance', check_regulatory_compliance)
graph.add_edge('validate_accuracy', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_accuracy')
graph = graph.compile()
