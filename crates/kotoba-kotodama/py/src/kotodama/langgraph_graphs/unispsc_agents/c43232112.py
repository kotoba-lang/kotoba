from langgraph.graph import StateGraph, END
from typing import TypedDict

class DTPState(TypedDict):
    license_key: str
    version: str
    validated: bool

def validate_software_version(state: DTPState):
    state['validated'] = state.get('version', '0.0') >= '2023.0'
    return state

def provision_license(state: DTPState):
    if state.get('validated'):
        print(f'Provisioning license for version {state.get('version')}')
    return state

graph = StateGraph(DTPState)
graph.add_node('validate', validate_software_version)
graph.add_node('provision', provision_license)
graph.add_edge('validate', 'provision')
graph.add_edge('provision', END)
graph.set_entry_point('validate')
graph = graph.compile()
