from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ResourceState(TypedDict):
    title: str
    age_group: str
    compliance_checked: bool

def validate_content(state: ResourceState):
    state['compliance_checked'] = 'religious_alignment' in state
    return state

def catalog_resource(state: ResourceState):
    print(f'Cataloging: {state.get('title')}')
    return state

graph = StateGraph(ResourceState)
graph.add_node('validate', validate_content)
graph.add_node('catalog', catalog_resource)
graph.set_entry_point('validate')
graph.add_edge('validate', 'catalog')
graph.add_edge('catalog', END)
graph = graph.compile()
