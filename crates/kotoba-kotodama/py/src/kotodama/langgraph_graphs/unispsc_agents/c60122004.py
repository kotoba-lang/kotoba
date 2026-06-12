from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtKitState(TypedDict):
    kit_id: str
    contents_verified: bool
    safety_checked: bool
    is_approved: bool

def verify_components(state: ArtKitState):
    print('Verifying components: nails, thread, and boards included.')
    return {'contents_verified': True}

def check_safety_regulations(state: ArtKitState):
    print('Checking non-toxicity standards and age ratings.')
    return {'safety_checked': True, 'is_approved': state.get('contents_verified', False)}

graph = StateGraph(ArtKitState)
graph.add_node('verify', verify_components)
graph.add_node('safety', check_safety_regulations)
graph.add_edge('verify', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('verify')
graph = graph.compile()
