from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalState(TypedDict):
    commodity_id: str
    purity_check_passed: bool
    safety_clearance: bool
    history: Annotated[List[str], operator.add]

def validate_safety(state: ChemicalState):
    # Simulate chemical safety verification logic
    return {'safety_clearance': True, 'history': ['Safety validated']}

def perform_quality_analysis(state: ChemicalState):
    # Simulate analytical purity validation
    return {'purity_check_passed': True, 'history': ['Quality analysis passed']}

graph = StateGraph(ChemicalState)
graph.add_node('safety_check', validate_safety)
graph.add_node('quality_analysis', perform_quality_analysis)
graph.add_edge('safety_check', 'quality_analysis')
graph.add_edge('quality_analysis', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
