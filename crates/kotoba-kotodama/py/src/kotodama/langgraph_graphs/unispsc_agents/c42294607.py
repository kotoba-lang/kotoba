from typing import TypedDict
from langgraph.graph import StateGraph, END

class ValveState(TypedDict):
    valve_id: str
    is_sterile: bool
    passed_qa: bool

def validate_sterile(state: ValveState):
    state['is_sterile'] = True
    return state

def check_quality(state: ValveState):
    state['passed_qa'] = state.get('is_sterile', False)
    return state

graph = StateGraph(ValveState)
graph.add_node('sterilization_check', validate_sterile)
graph.add_node('qa_inspection', check_quality)
graph.set_entry_point('sterilization_check')
graph.add_edge('sterilization_check', 'qa_inspection')
graph.add_edge('qa_inspection', END)
graph = graph.compile()
