from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END

class MineralChemicalState(TypedDict):
    batch_id: str
    purity: float
    status: str
    validation_log: Sequence[str]

def validate_purity(state: MineralChemicalState):
    log = list(state.get('validation_log', []))
    if state.get('purity', 0) < 95.0:
        return {'status': 'REJECTED', 'validation_log': log + ['Low purity detected']}
    return {'status': 'VALIDATED', 'validation_log': log + ['Purity check passed']}

def process_procurement(state: MineralChemicalState):
    log = list(state.get('validation_log', []))
    return {'status': 'READY_FOR_SHIPMENT', 'validation_log': log + ['Procurement processing finalized']}

graph = StateGraph(MineralChemicalState)
graph.add_node('validate', validate_purity)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
