from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class ArgonState(TypedDict):
    purity_req: float
    cylinder_id: str
    validation_log: Annotated[Sequence[str], operator.add]
    status: str

def validate_purity(state: ArgonState):
    purity = state.get('purity_req', 0.0)
    if purity >= 99.999:
        return {'validation_log': ['High-purity grade verified'], 'status': 'valid'}
    return {'validation_log': ['Purity insufficient for target application'], 'status': 'rejected'}

def check_cylinder_integrity(state: ArgonState):
    return {'validation_log': ['Cylinder structural integrity checked'], 'status': 'ready'}

graph = StateGraph(ArgonState)
graph.add_node('validate', validate_purity)
graph.add_node('integrity', check_cylinder_integrity)
graph.set_entry_point('validate')
graph.add_edge('validate', 'integrity')
graph.add_edge('integrity', END)
graph = graph.compile()
