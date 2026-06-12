from typing import TypedDict
from langgraph.graph import StateGraph, END

class ResistorState(TypedDict):
    part_number: str
    spec_sheet_url: str
    is_compliant: bool
    validation_log: list

def validate_specs(state: ResistorState):
    log = []
    if not state.get('spec_sheet_url'):
        log.append('Missing spec sheet')
    return {'is_compliant': len(log) == 0, 'validation_log': log}

def export_review(state: ResistorState):
    return {'validation_log': state['validation_log'] + ['Dual-use export check completed']}

graph = StateGraph(ResistorState)
graph.add_node('validate', validate_specs)
graph.add_node('export_control', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_control')
graph.add_edge('export_control', END)
graph = graph.compile()
