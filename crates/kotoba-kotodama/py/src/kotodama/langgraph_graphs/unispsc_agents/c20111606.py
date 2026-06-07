from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    part_id: str
    material_certified: bool
    passed_inspection: bool
    final_status: str

def validate_material(state: ProcessingState):
    return {'material_certified': True}

def perform_inspection(state: ProcessingState):
    return {'passed_inspection': True, 'final_status': 'APPROVED'}

def finalize_part(state: ProcessingState):
    return {'final_status': 'COMPLETED'}

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', perform_inspection)
graph.add_node('finalize', finalize_part)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
