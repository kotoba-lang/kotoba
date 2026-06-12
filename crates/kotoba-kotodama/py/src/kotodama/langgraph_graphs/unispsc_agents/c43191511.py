from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class GraphicsProcessingState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_log: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_gpu_specs(state: GraphicsProcessingState):
    specs = state.get('specifications', {})
    log = []
    compliant = True
    if specs.get('vram_capacity_gb', 0) < 4:
        log.append('Insufficient VRAM for professional CAD/Rendering')
        compliant = False
    return {'validation_log': log, 'is_compliant': compliant}

def routing_node(state: GraphicsProcessingState):
    return 'validate' if state['is_compliant'] else END

graph = StateGraph(GraphicsProcessingState)
graph.add_node('validate', validate_gpu_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
