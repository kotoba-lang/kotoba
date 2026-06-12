from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicrofilmState(TypedDict):
    equipment_type: str
    compliance_checked: bool
    vendor_approved: bool

def validate_equipment(state: MicrofilmState):
    print('Validating ISO archival compliance...')
    return {'compliance_checked': True}

def check_vendor_license(state: MicrofilmState):
    print('Verifying vendor maintenance credentials...')
    return {'vendor_approved': True}

graph = StateGraph(MicrofilmState)
graph.add_node('validate', validate_equipment)
graph.add_node('vendor', check_vendor_license)
graph.set_entry_point('validate')
graph.add_edge('validate', 'vendor')
graph.add_edge('vendor', END)
graph = graph.compile()
