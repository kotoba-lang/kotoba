from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PestDetectionState(TypedDict):
    crop_image_data: bytes
    sensor_metrics: dict
    analysis_results: dict
    risk_score: float

def ingest_sensor_data(state: PestDetectionState) -> PestDetectionState:
    state['analysis_results'] = {'status': 'processed'}
    return state

def run_ai_inference(state: PestDetectionState) -> PestDetectionState:
    state['risk_score'] = 0.85
    return state

def evaluate_risk(state: PestDetectionState) -> str:
    return 'alert' if state['risk_score'] > 0.8 else 'monitor'

graph = StateGraph(PestDetectionState)
graph.add_node('ingest', ingest_sensor_data)
graph.add_node('inference', run_ai_inference)
graph.add_edge('ingest', 'inference')
graph.add_conditional_edges('inference', evaluate_risk, {'alert': END, 'monitor': END})
graph.set_entry_point('ingest')
graph = graph.compile()
