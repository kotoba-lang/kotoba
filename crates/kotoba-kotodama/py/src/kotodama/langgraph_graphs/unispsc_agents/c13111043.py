from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class ProcurementState(TypedDict):
    material_type: str
    quality_report: dict
    approved: bool
    logs: Annotated[List[str], operator.add]

def validate_quality(state: ProcurementState):
    report = state.get('quality_report', {})
    is_compliant = report.get('moisture', 100) < 5.0 and report.get('leaching_ok', False)
    return {'approved': is_compliant, 'logs': ['Quality validation completed']}

def route_logistics(state: ProcurementState):
    if state['approved']:
        return 'approve'
    return 'flag_for_review'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
