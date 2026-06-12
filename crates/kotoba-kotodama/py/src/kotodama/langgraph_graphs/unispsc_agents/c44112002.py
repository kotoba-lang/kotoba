from typing import TypedDict
from langgraph.graph import StateGraph, END

class CalendarState(TypedDict):
    order_id: str
    spec_verified: bool
    vendor_approved: bool

def validate_specs(state: CalendarState):
    print('Validating paper quality and print specs...')
    state['spec_verified'] = True
    return state

def check_vendor(state: CalendarState):
    print('Verifying vendor sustainability credentials...')
    state['vendor_approved'] = True
    return state

graph = StateGraph(CalendarState)
graph.add_node('validate', validate_specs)
graph.add_node('vendor', check_vendor)
graph.add_edge('validate', 'vendor')
graph.add_edge('vendor', END)
graph.set_entry_point('validate')
graph = graph.compile()
