from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotAssemblyState(TypedDict):
    task_id: str
    assembly_steps: List[str]
    validation_logs: List[str]
    is_approved: bool

def validate_kinematics(state: RobotAssemblyState) -> RobotAssemblyState:
    print(f'Validating kinematics for task {state.get(task_id)}')
    state['validation_logs'].append('Kinematics validated')
    return state

def execute_assembly(state: RobotAssemblyState) -> RobotAssemblyState:
    print('Executing robotic assembly sequence')
    state['validation_logs'].append('Assembly completed')
    state['is_approved'] = True
    return state

graph = StateGraph(RobotAssemblyState)
graph.add_node('validate', validate_kinematics)
graph.add_node('execute', execute_assembly)
graph.set_entry_point('validate')
graph.add_edge('validate', 'execute')
graph.add_edge('execute', END)
graph = graph.compile()
