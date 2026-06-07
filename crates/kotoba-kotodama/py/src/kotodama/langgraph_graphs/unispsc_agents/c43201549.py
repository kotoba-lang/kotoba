from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class AutomationState(TypedDict):
    tasks: Annotated[Sequence[str], operator.add]
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_robot_task(state: AutomationState):
    task = state['tasks'][-1]
    return {'validation_log': [f'Validating task: {task}'], 'status': 'validated'}

def execute_task(state: AutomationState):
    return {'validation_log': ['Task execution completed successfully'], 'status': 'completed'}

builder = StateGraph(AutomationState)
builder.add_node('validator', validate_robot_task)
builder.add_node('executor', execute_task)
builder.add_edge('validator', 'executor')
builder.add_edge('executor', END)
builder.set_entry_point('validator')
graph = builder.compile()
