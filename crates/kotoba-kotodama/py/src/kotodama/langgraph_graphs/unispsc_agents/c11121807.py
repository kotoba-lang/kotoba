from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalState(TypedDict):
    commodity_code: str
    purity_cert: str
    safety_check_passed: bool
    logistics_route: List[str]

def validate_safety(state: ChemicalState):
    # Simulate regulatory check for hazardous material
    return {'safety_check_passed': True}

def route_logistics(state: ChemicalState):
    # Logic for hazardous material handling
    return {'logistics_route': ['hazmat_certified_carrier', 'climate_control_depot']}

def build_graph():
    graph = StateGraph(ChemicalState)
    graph.add_node('safety_check', validate_safety)
    graph.add_node('logistics', route_logistics)
    graph.add_edge('safety_check', 'logistics')
    graph.add_edge('logistics', END)
    graph.set_entry_point('safety_check')
    return graph.compile()

graph = build_graph()
