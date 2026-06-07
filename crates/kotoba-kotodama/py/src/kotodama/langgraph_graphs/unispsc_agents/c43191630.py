from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ImageProcState(TypedDict):
    input_data: str
    validation_log: Annotated[Sequence[str], operator.add]
    processing_result: str

def validate_image_module(state: ImageProcState):
    log = [f'Validating hardware specs for {state[input_data]}']
    return {validation_log: log}

def execute_processing(state: ImageProcState):
    return {processing_result: 'optimized_graphics_pipeline_active'}

graph = StateGraph(ImageProcState)
graph.add_node('validate', validate_image_module)
graph.add_node('process', execute_processing)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
