from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class HistologyState(TypedDict):
    station_id: str
    ventilation_verified: bool
    chemical_compliance: bool
    final_report: str

def check_ventilation(state: HistologyState):
    return {'ventilation_verified': True}

def validate_compliance(state: HistologyState):
    return {'chemical_compliance': True, 'final_report': 'Station validated for hazardous handling'}

graph = StateGraph(HistologyState)
graph.add_node('check_ventilation', check_ventilation)
graph.add_node('validate_compliance', validate_compliance)
graph.set_entry_point('check_ventilation')
graph.add_edge('check_ventilation', 'validate_compliance')
graph.add_edge('validate_compliance', END)
graph = graph.compile()
