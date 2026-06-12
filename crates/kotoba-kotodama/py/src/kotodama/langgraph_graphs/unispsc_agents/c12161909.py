from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    commodity_code: str
    purity_check: bool
    hazard_level: int
    history: Annotated[Sequence[str], operator.add]

def validate_purity(state: ChemicalState):
    # Simulate purity verification
    return {'purity_check': True, 'history': ['Purity validation passed']}

def assess_hazard(state: ChemicalState):
    # Simulate hazard assessment
    return {'hazard_level': 3, 'history': ['Hazard assessment complete']}

def finalize_procurement(state: ChemicalState):
    # Finalize procurement state
    return {'history': ['Procurement order prepared']}

builder = StateGraph(ChemicalState)
builder.add_node('purity', validate_purity)
builder.add_node('hazard', assess_hazard)
builder.add_node('finalize', finalize_procurement)
builder.set_entry_point('purity')
builder.add_edge('purity', 'hazard')
builder.add_edge('hazard', 'finalize')
builder.add_edge('finalize', END)
graph = builder.compile()
