from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    content_material: str
    compliance_report: str

def validate_curriculum(state: State) -> State:
    print(f'Validating: {state[content_material]}')
    return {compliance_report: 'Curriculum standards verified'}

def format_output(state: State) -> State:
    return {compliance_report: f'Certified: {state[compliance_report]}'}

graph = StateGraph(State)
graph.add_node('validate', validate_curriculum)
graph.add_node('format', format_output)
graph.set_entry_point('validate')
graph.add_edge('validate', 'format')
graph.add_edge('format', END)

graph = graph.compile()
