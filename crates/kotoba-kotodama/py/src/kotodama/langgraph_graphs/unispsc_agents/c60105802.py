from typing import TypedDict
from langgraph.graph import StateGraph, END

class SewingProjectState(TypedDict):
    material_list: list
    validation_results: dict

def validate_materials(state: SewingProjectState):
    # Simulate material compliance check
    return {'validation_results': {'status': 'approved', 'reasons': 'standards met'}}

def generate_report(state: SewingProjectState):
    return {'validation_results': {'status': 'finalized'}}

builder = StateGraph(SewingProjectState)
builder.add_node('validate', validate_materials)
builder.add_node('report', generate_report)
builder.add_edge('validate', 'report')
builder.add_edge('report', END)
builder.set_entry_point('validate')
graph = builder.compile()
