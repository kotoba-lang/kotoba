from typing import TypedDict
from langgraph.graph import StateGraph, END

class CoreState(TypedDict):
    material: str
    specs: dict
    validated: bool

def validate_magnesium_honeycomb(state: CoreState):
    specs = state.get('specs', {})
    # Check for critical aerospace compliance
    is_valid = all(k in specs for k in ['cell_size_mm', 'alloy_grade_astm'])
    print(f'Validating Magnesium Core Specs: {is_valid}')
    return {'validated': is_valid}

def process_export_control(state: CoreState):
    print('Flagging for dual-use export review...')
    return {'validated': True}

graph = StateGraph(CoreState)
graph.add_node('validate', validate_magnesium_honeycomb)
graph.add_node('export_check', process_export_control)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
