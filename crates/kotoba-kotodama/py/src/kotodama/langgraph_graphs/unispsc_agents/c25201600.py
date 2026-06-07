from typing import TypedDict
from langgraph.graph import StateGraph, END

class AerospaceState(TypedDict):
    part_number: str
    compliance_docs: list[str]
    export_license_required: bool

def validate_specs(state: AerospaceState):
    print('Validating AS9100 compliance for precision navigation components...')
    return {'compliance_docs': ['ISO9001', 'AS9100']}

def check_export_controls(state: AerospaceState):
    print('Checking dual-use export control classification...')
    return {'export_license_required': True}

graph = StateGraph(AerospaceState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
