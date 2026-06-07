from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ActuatorState(TypedDict):
    specs: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: ActuatorState):
    specs = state.get('specs', {})
    logs = []
    if specs.get('torque_rating_nm', 0) <= 0:
        logs.append('Invalid torque rating')
    return {'validation_logs': logs, 'is_approved': len(logs) == 0}

def compile_graph():
    graph = StateGraph(ActuatorState)
    graph.add_node('validate', validate_specs)
    graph.add_edge('validate', END)
    graph.set_entry_point('validate')
    return graph.compile()

graph = compile_graph()
