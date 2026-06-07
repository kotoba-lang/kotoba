from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ChemicalProcurementState(TypedDict):
    batch_id: str
    safety_check_passed: bool
    compliance_tags: List[str]
    log: Annotated[List[str], operator.add]

def validate_safety_data(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Specialized logic for chemical safety validation
    passed = len(state.get('batch_id', '')) > 0
    return {'safety_check_passed': passed, 'log': ['Safety data verified']}

def compliance_review(state: ChemicalProcurementState) -> ChemicalProcurementState:
    # Dual-use and sanctions check logic
    return {'compliance_tags': ['review_complete'], 'log': ['Compliance review finalized']}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('safety', validate_safety_data)
graph.add_node('compliance', compliance_review)
graph.set_entry_point('safety')
graph.add_edge('safety', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
