from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SoftwareState(TypedDict):
    tasks: Annotated[Sequence[str], operator.add]
    status: str

def validate_software_config(state: SoftwareState):
    return {'status': 'validated'}

def deploy_infrastructure(state: SoftwareState):
    return {'status': 'deployed'}

def monitor_deployment(state: SoftwareState):
    return {'status': 'monitored'}

builder = StateGraph(SoftwareState)
builder.add_node('validate', validate_software_config)
builder.add_node('deploy', deploy_infrastructure)
builder.add_node('monitor', monitor_deployment)
builder.set_entry_point('validate')
builder.add_edge('validate', 'deploy')
builder.add_edge('deploy', 'monitor')
builder.add_edge('monitor', END)
graph = builder.compile()
