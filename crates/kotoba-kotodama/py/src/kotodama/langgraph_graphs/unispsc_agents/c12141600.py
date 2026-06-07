from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ChemicalState(TypedDict):
    commodity_code: str
    purity_check: bool
    safety_compliance: bool
    messages: Annotated[List[str], add_messages]

def validate_purity(state: ChemicalState):
    # Simulate spectroscopic verification logic
    purity = 99.9
    return {'purity_check': purity >= 99.5}

def check_msds(state: ChemicalState):
    # Simulate safety documentation check
    return {'safety_compliance': True}

graph = StateGraph(ChemicalState)
graph.add_node('verify_purity', validate_purity)
graph.add_node('safety_check', check_msds)
graph.add_edge('verify_purity', 'safety_check')
graph.add_edge('safety_check', END)
graph.set_entry_point('verify_purity')
graph = graph.compile()
