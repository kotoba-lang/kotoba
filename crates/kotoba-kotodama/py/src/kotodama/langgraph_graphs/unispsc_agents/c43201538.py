from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class NetworkState(TypedDict):
    node_list: Annotated[Sequence[str], operator.add]
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_nodes(state: NetworkState):
    # Simulate fine-grained network node validation logic
    logs = [f'Validating node {n}' for n in state['node_list']]
    return {'validation_logs': logs, 'is_compliant': True}

def optimize_graph(state: NetworkState):
    # Simulate optimization workflow step
    return {'validation_logs': ['Optimization routine applied to infrastructure']}

def graph_init():
    workflow = StateGraph(NetworkState)
    workflow.add_node('validate', validate_nodes)
    workflow.add_node('optimize', optimize_graph)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', 'optimize')
    workflow.add_edge('optimize', END)
    return workflow.compile()

graph = graph_init()
