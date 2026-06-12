from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class HarvesterState(TypedDict):
    crop_type: str
    quality_metrics: dict
    workflow_steps: Annotated[List[str], add_messages]

def sense_quality(state: HarvesterState):
    return {'workflow_steps': ['sensor_scan', 'image_classification']}

def process_harvest(state: HarvesterState):
    return {'workflow_steps': ['automated_culling', 'robotic_storage']}

builder = StateGraph(HarvesterState)
builder.add_node('sense', sense_quality)
builder.add_node('process', process_harvest)
builder.set_entry_point('sense')
builder.add_edge('sense', 'process')
builder.add_edge('process', END)
graph = builder.compile()
