from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_certified: bool
    dimensional_check_passed: bool
    inspection_report_generated: bool

def validate_material(state: ForgingState):
    print('Validating forging material specs...')
    return {'material_certified': True}

def validate_dimensions(state: ForgingState):
    print('Checking dimensional tolerances for rolled ring...')
    return {'dimensional_check_passed': True}

def generate_report(state: ForgingState):
    print('Compiling mill test and machining report...')
    return {'inspection_report_generated': True}

graph = StateGraph(ForgingState)
graph.add_node('material', validate_material)
graph.add_node('dimensions', validate_dimensions)
graph.add_node('report', generate_report)
graph.set_entry_point('material')
graph.add_edge('material', 'dimensions')
graph.add_edge('dimensions', 'report')
graph.add_edge('report', END)
graph = graph.compile()
