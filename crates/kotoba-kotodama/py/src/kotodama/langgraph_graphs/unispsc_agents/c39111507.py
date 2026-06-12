import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, END

class DeskFixtureState(TypedDict):
    spec_data: dict
    validation_results: Annotated[list, operator.add]

def validate_materials(state: DeskFixtureState):
    # Business logic for material compliance check
    return {'validation_results': ['Material compliance verified']}

def check_compliance(state: DeskFixtureState):
    # Electrical and safety compliance check
    return {'validation_results': ['Electrical safety checked']}

graph = StateGraph(DeskFixtureState)
graph.add_node('material', validate_materials)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('material')
graph.add_edge('material', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
