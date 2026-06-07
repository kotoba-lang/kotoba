from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MineralState(TypedDict):
    ore_type: str
    purity_check: bool
    compliance_score: float
    logs: Annotated[List[str], add_messages]

def validate_ore(state: MineralState) -> MineralState:
    # Simulate chemical assay verification
    state['purity_check'] = True
    state['logs'].append('Assay verified for mineral 11151713')
    return state

def check_compliance(state: MineralState) -> MineralState:
    # Sanctions and export control check
    state['compliance_score'] = 0.95
    state['logs'].append('Compliance check passed')
    return state

graph = StateGraph(MineralState)
graph.add_node('validate', validate_ore)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
