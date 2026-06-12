from typing import TypedDict
from langgraph.graph import StateGraph, END

class GutterState(TypedDict):
    spec_data: dict
    validation_report: list

def validate_materials(state: GutterState):
    # logic to check material compliance against standard
    return {'validation_report': ['Material pass']}

def check_dimensions(state: GutterState):
    # logic for structural sizing
    return {'validation_report': state['validation_report'] + ['Dimension check complete']}

graph = StateGraph(GutterState)
graph.add_node('MaterialValidation', validate_materials)
graph.add_node('DimensionCheck', check_dimensions)
graph.set_entry_point('MaterialValidation')
graph.add_edge('MaterialValidation', 'DimensionCheck')
graph.add_edge('DimensionCheck', END)
graph = graph.compile()
