from typing import TypedDict
from langgraph.graph import StateGraph, END

class RadioDataState(TypedDict):
    equipment_id: str
    frequency_validated: bool
    compliance_checked: bool

def validate_frequency(state: RadioDataState):
    print('Validating RF frequency compliance...')
    return {'frequency_validated': True}

def check_compliance(state: RadioDataState):
    print('Performing export control and radio cert check...')
    return {'compliance_checked': True}

graph = StateGraph(RadioDataState)
graph.add_node('freq_val', validate_frequency)
graph.add_node('comp_check', check_compliance)
graph.set_entry_point('freq_val')
graph.add_edge('freq_val', 'comp_check')
graph.add_edge('comp_check', END)
graph = graph.compile()
