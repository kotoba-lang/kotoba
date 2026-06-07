from typing import TypedDict
from langgraph.graph import StateGraph, END

class ElastometerState(TypedDict):
    spec: dict
    validated: bool
    error_log: list

def validate_specs(state: ElastometerState):
    s = state['spec']
    valid = 'load_capacity_n' in s and 'compliance_iso_37' in s
    return {'validated': valid, 'error_log': [] if valid else ['Missing technical fields']}

def route_by_validation(state: ElastometerState):
    return 'process' if state['validated'] else END

def process_procurement(state: ElastometerState):
    return {'error_log': state['error_log'] + ['Procurement workflow initiated']}

graph = StateGraph(ElastometerState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', route_by_validation)
graph.add_edge('process', END)
graph.set_entry_point('validate')
# Note: compile not called as it requires defined state schema and nodes structure established here.

graph = graph.compile()
