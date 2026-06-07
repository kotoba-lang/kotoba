from langgraph.graph import StateGraph, END
from typing import TypedDict

class TabletState(TypedDict):
    spec_sheet: dict
    validation_status: bool
    compliance_report: str

def validate_specs(state: TabletState):
    tablet = state.get('spec_sheet', {})
    is_valid = all(k in tablet for k in ['cpu', 'ram', 'storage'])
    return {'validation_status': is_valid, 'compliance_report': 'Validated' if is_valid else 'Missing specs'}

def enterprise_config_check(state: TabletState):
    return {'compliance_report': 'Configured for MDM'}

graph = StateGraph(TabletState)
graph.add_node('validate', validate_specs)
graph.add_node('config', enterprise_config_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'config')
graph.add_edge('config', END)
graph = graph.compile()
