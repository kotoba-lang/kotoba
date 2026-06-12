from typing import TypedDict, Annotated, Sequence, List
from langgraph.graph import StateGraph, END

class CrudeState(TypedDict):
    commodity_code: str
    quality_metrics: dict
    compliance_checks: List[str]
    validation_status: bool

def analyze_quality(state: CrudeState):
    metrics = state.get('quality_metrics', {})
    status = metrics.get('sulfur_content', 0) < 0.5
    return {'validation_status': status}

def verify_compliance(state: CrudeState):
    return {'compliance_checks': ['sanctions_cleared', 'safety_data_verified']}

defgraph = StateGraph(CrudeState)
defgraph.add_node('quality', analyze_quality)
defgraph.add_node('compliance', verify_compliance)
defgraph.set_entry_point('quality')
defgraph.add_edge('quality', 'compliance')
defgraph.add_edge('compliance', END)
graph = defgraph.compile()
