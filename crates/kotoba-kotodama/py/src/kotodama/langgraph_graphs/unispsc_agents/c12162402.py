from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    batch_id: str
    purity_check: float
    viscosity_validation: bool
    compliance_tags: Annotated[Sequence[str], operator.add]

def validate_purity(state: ResinState) -> ResinState:
    # Logic to verify chemical purity standards
    if state.get('purity_check', 0) > 0.99:
        return {'compliance_tags': ['purity_verified']}
    return {'compliance_tags': ['purity_flagged']}

def validate_viscosity(state: ResinState) -> ResinState:
    # Logic to verify viscosity specs
    return {'viscosity_validation': True}

graph = StateGraph(ResinState)
graph.add_node('check_purity', validate_purity)
graph.add_node('check_viscosity', validate_viscosity)
graph.set_entry_point('check_purity')
graph.add_edge('check_purity', 'check_viscosity')
graph.add_edge('check_viscosity', END)
graph = graph.compile()
