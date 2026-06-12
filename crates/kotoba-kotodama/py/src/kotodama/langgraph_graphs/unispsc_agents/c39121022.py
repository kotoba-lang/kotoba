from typing import TypedDict
from langgraph.graph import StateGraph, END

class TransformerState(TypedDict):
    specs: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: TransformerState):
    specs = state.get('specs', {})
    required = ['voltage', 'power', 'efficiency']
    compliant = all(k in specs for k in required)
    return {'is_compliant': compliant, 'validation_log': ['Specs checked'] if compliant else ['Missing fields']}

def route_by_compliance(state: TransformerState):
    return 'process' if state.get('is_compliant') else END

graph = StateGraph(TransformerState)
graph.add_node('validate', validate_specs)
graph.add_node('process', lambda s: {'validation_log': s['validation_log'] + ['Processing transformer data']})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph = graph.compile()
