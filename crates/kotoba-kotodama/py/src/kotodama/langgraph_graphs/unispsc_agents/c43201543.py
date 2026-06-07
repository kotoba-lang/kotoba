from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ServerState(TypedDict):
    tasks: Annotated[Sequence[str], operator.add]
    status: str

def validate_infra_config(state: ServerState):
    return {'status': 'validated'}

def deploy_server(state: ServerState):
    return {'status': 'deployed'}

def monitor_deployment(state: ServerState):
    return {'status': 'monitoring'}

graph = StateGraph(ServerState)
graph.add_node('validate', validate_infra_config)
graph.add_node('deploy', deploy_server)
graph.add_node('monitor', monitor_deployment)
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', 'monitor')
graph.add_edge('monitor', END)
graph.set_entry_point('validate')
graph = graph.compile()
