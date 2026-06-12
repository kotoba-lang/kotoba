from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class UnderpassState(TypedDict):
    project_id: str
    structural_specs: dict
    validation_errors: List[str]
    approved: bool

def validate_geotechnical(state: UnderpassState):
    print('Validating soil survey data...')
    return {'validation_errors': []}

def structural_review(state: UnderpassState):
    print('Checking structural integrity specs...')
    return {'approved': True}

graph = StateGraph(UnderpassState)
graph.add_node('geotech_check', validate_geotechnical)
graph.add_node('structural_review', structural_review)
graph.set_entry_point('geotech_check')
graph.add_edge('geotech_check', 'structural_review')
graph.add_edge('structural_review', END)
graph = graph.compile()
