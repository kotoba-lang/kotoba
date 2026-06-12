from typing import TypedDict
from langgraph.graph import StateGraph, END

class ParkProcurementState(TypedDict):
    site_survey_done: bool
    permits_approved: bool
    design_validated: bool

def check_site_survey(state: ParkProcurementState):
    return {'site_survey_done': True}

def validate_design(state: ParkProcurementState):
    return {'design_validated': True}

graph = StateGraph(ParkProcurementState)
graph.add_node('survey', check_site_survey)
graph.add_node('design', validate_design)
graph.add_edge('survey', 'design')
graph.add_edge('design', END)
graph.set_entry_point('survey')
graph = graph.compile()
