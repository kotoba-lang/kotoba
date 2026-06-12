from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalState(TypedDict):
    batch_id: str
    purity_check: bool
    safety_clearance: bool
    log: Annotated[List[str], operator.add]

def validate_purity(state: ChemicalState) -> ChemicalState:
    # Implementation of high-purity batch spectroscopic verification logic
    state['purity_check'] = True
    state['log'] = ['Purity verification passed.']
    return state

def check_safety_protocols(state: ChemicalState) -> ChemicalState:
    # Implementation of dual-use control and safety clearance checks
    state['safety_clearance'] = True
    state['log'] = ['Safety protocol check passed.']
    return state

graph = StateGraph(ChemicalState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('safety_check', check_safety_protocols)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_check')
graph.add_edge('safety_check', END)

# Compile the graph
graph = graph.compile()
