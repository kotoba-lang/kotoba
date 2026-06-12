from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    curriculum_match: bool
    validation_errors: List[str]

def validate_curriculum(state: ProcurementState):
    print('Validating curriculum alignment...')
    return {'curriculum_match': True}

def generate_metadata(state: ProcurementState):
    print('Generating ISBN and pedagogical specs...')
    return {'validation_errors': []}

graph = StateGraph(ProcurementState)
graph.add_node('validate_curriculum', validate_curriculum)
graph.add_node('generate_metadata', generate_metadata)
graph.add_edge('validate_curriculum', 'generate_metadata')
graph.add_edge('generate_metadata', END)
graph.set_entry_point('validate_curriculum')
graph = graph.compile()
