from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WorkflowState(TypedDict):
    content_type: str
    validation_checks: List[str]
    approved: bool

def validate_metadata(state: WorkflowState):
    checks = ['age_appropriateness', 'curriculum_alignment', 'print_quality']
    return {'validation_checks': checks, 'approved': True}

def process_content(state: WorkflowState):
    print('Processing activity book specifications...')
    return {'approved': True}

graph = StateGraph(WorkflowState)
graph.add_node('validate', validate_metadata)
graph.add_node('process', process_content)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
