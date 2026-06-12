from typing import TypedDict
from langgraph.graph import StateGraph, END

class EarmoldState(TypedDict):
    order_id: str
    impression_data: dict
    validation_passed: bool

def validate_impression(state: EarmoldState):
    print('Validating ear impression geometry')
    return {'validation_passed': True}

def route_production(state: EarmoldState):
    return 'production' if state['validation_passed'] else END

graph = StateGraph(EarmoldState)
graph.add_node('validate', validate_impression)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
