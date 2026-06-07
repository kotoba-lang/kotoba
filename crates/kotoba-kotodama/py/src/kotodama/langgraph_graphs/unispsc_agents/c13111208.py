from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CrudeOilState(TypedDict):
    commodity_code: str
    batch_id: str
    quality_metrics: dict
    workflow_steps: Annotated[List[str], operator.add]
    is_cleared: bool

def validate_quality(state: CrudeOilState):
    metrics = state.get('quality_metrics', {})
    sulfur = metrics.get('sulfur_content', 0.0)
    is_cleared = sulfur < 0.5
    return {'is_cleared': is_cleared, 'workflow_steps': ['quality_validation_complete']}

def route_logistics(state: CrudeOilState):
    if state['is_cleared']:
        return 'process_refinery'
    return 'quarantine'

def process_refinery(state: CrudeOilState):
    return {'workflow_steps': ['refinery_processing_initiated']}

def quarantine(state: CrudeOilState):
    return {'workflow_steps': ['quarantine_protocol_triggered']}

graph = StateGraph(CrudeOilState)
graph.add_node('validate', validate_quality)
graph.add_node('process_refinery', process_refinery)
graph.add_node('quarantine', quarantine)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_logistics, {'process_refinery': 'process_refinery', 'quarantine': 'quarantine'})
graph.add_edge('process_refinery', END)
graph.add_edge('quarantine', END)
graph = graph.compile()
