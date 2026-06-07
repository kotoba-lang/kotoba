from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ContainerState(TypedDict):
    material_spec: str
    quality_checks: List[str]
    validation_passed: bool

def validate_material(state: ContainerState):
    # Simulate material compliance check
    return {'validation_passed': True}

def perform_quality_inspection(state: ContainerState):
    # Simulate structural integrity inspection
    return {'quality_checks': ['tensile_test_ok', 'moisture_test_ok']}

graph = StateGraph(ContainerState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', perform_quality_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)

# Compile the graph
graph = graph.compile()
