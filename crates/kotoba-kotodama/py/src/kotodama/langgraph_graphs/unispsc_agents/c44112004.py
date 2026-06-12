from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MeetingToolState(TypedDict):
    requirements: List[str]
    compliance_check: bool
    final_config: dict

def validate_requirements(state: MeetingToolState):
    print('Validating technical specifications...')
    return {'compliance_check': True}

def generate_config(state: MeetingToolState):
    print('Generating software configuration...')
    return {'final_config': {'integrations': ['Outlook', 'Teams']}}

graph = StateGraph(MeetingToolState)
graph.add_node('validate', validate_requirements)
graph.add_node('configure', generate_config)
graph.set_entry_point('validate')
graph.add_edge('validate', 'configure')
graph.add_edge('configure', END)
graph = graph.compile()
