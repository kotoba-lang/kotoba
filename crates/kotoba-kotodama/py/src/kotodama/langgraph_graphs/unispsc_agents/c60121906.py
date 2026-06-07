from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PrintState(TypedDict):
    material_type: str
    specifications: dict
    validation_passed: bool
    error_log: List[str]

def validate_materials(state: PrintState):
    specs = state.get('specifications', {})
    valid = 'shelf_life' in specs and 'sensitivity' in specs
    return {'validation_passed': valid}

def process_procurement(state: PrintState):
    if state['validation_passed']:
        print('Proceeding with procurement order')
    return {}

graph = StateGraph(PrintState)
graph.add_node('validate', validate_materials)
graph.add_node('order', process_procurement)
graph.add_edge('validate', 'order')
graph.add_edge('order', END)
graph.set_entry_point('validate')
graph = graph.compile()
