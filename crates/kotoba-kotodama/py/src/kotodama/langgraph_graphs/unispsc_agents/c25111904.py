from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PaddleState(TypedDict):
    specifications: dict
    validation_passed: bool
    inspection_report: str

def validate_material(state: PaddleState):
    material = state.get('specifications', {}).get('material', 'unknown')
    is_valid = material in ['stainless_steel', 'reinforced_composite']
    return {'validation_passed': is_valid}

def generate_report(state: PaddleState):
    status = 'APPROVED' if state['validation_passed'] else 'REJECTED'
    return {'inspection_report': f'Paddle procurement validation: {status}'}

graph = StateGraph(PaddleState)
graph.add_node('validate', validate_material)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)

graph = graph.compile()
