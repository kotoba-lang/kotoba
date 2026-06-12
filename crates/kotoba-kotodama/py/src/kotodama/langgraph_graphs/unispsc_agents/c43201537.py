from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    task_id: str
    sub_tasks: List[str]
    status: str

def node_init_task(state: AgentState):
    return {'status': 'initializing'}

def node_process_subtasks(state: AgentState):
    return {'status': 'processing'}

def node_finalize(state: AgentState):
    return {'status': 'complete'}

builder = StateGraph(AgentState)
builder.add_node('init', node_init_task)
builder.add_node('process', node_process_subtasks)
builder.add_node('final', node_finalize)
builder.add_edge('init', 'process')
builder.add_edge('process', 'final')
builder.add_edge('final', END)
builder.set_entry_point('init')
graph = builder.compile()
