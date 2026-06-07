from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ConnectionState(TypedDict):
    specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: ConnectionState):
    specs = state.get('specs', {})
    required = ['rated_voltage_v', 'rated_current_a', 'wire_gauge_awg']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed, 'error_log': [] if passed else ['Missing required specifications']}

def compile_graph():
    graph = StateGraph(ConnectionState)
    graph.add_node('validate', validate_specs)
    graph.set_entry_point('validate')
    graph.add_edge('validate', END)
    return graph.compile()

graph = compile_graph()
