from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class MineralState(TypedDict):
    raw_input: str
    purity_check: float
    spec_compliance: bool
    log: Annotated[List[str], operator.add]

def validate_purity(state: MineralState):
    # Simulate purity validation for industrial minerals
    purity = state.get('purity_check', 0.0)
    compliant = purity >= 98.5
    return {'spec_compliance': compliant, 'log': [f'Purity check at {purity}%: {compliant}']}

def process_material(state: MineralState):
    if state['spec_compliance']:
        return {'log': ['Proceeding to standard mineral distribution chain']}
    return {'log': ['Flagging for quality review due to purity failure']}

graph = StateGraph(MineralState)
graph.add_node('validate', validate_purity)
graph.add_node('process', process_material)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
