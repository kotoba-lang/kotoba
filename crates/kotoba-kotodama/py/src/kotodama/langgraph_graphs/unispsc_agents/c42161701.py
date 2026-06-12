from typing import TypedDict
from langgraph.graph import StateGraph, END

class HemofilterState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: HemofilterState):
    specs = state.get('spec_data', {})
    required = ['membrane_material', 'sterilization_date']
    is_compliant = all(k in specs for k in required)
    return {'is_compliant': is_compliant, 'validation_log': ['Specs checked'] if is_compliant else ['Missing fields']}

def process_procurement(state: HemofilterState):
    print('Processing hemofilter procurement...')
    return {'validation_log': state['validation_log'] + ['Procurement approved']}

graph = StateGraph(HemofilterState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
