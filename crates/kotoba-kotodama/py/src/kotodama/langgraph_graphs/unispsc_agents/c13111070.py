from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class LubricantState(TypedDict):
    lubricant_id: str
    spec_compliance: bool
    safety_score: int
    actions: Annotated[Sequence[str], operator.add]

def validate_viscosity(state: LubricantState):
    # Simulate viscosity validation logic
    return {'actions': ['Viscosity verified against ISO standards'], 'spec_compliance': True}

def assess_safety(state: LubricantState):
    # Simulate safety assessment logic
    return {'actions': ['Safety data sheet reviewed'], 'safety_score': 95}

graph = StateGraph(LubricantState)
graph.add_node('validate', validate_viscosity)
graph.add_node('safety', assess_safety)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph = graph.compile()
