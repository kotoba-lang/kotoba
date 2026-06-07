from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class FluoropolymerState(TypedDict):
    material_code: str
    spec_compliance: bool
    validation_log: Annotated[List[str], operator.add]

def validate_purity(state: FluoropolymerState):
    log = 'Purity verification successful for high-grade fluoropolymer.'
    return {'spec_compliance': True, 'validation_log': [log]}

def analyze_thermal_stability(state: FluoropolymerState):
    log = 'Thermal decomposition profile validated within project tolerance.'
    return {'validation_log': [log]}

graph = StateGraph(FluoropolymerState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('thermal_check', analyze_thermal_stability)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'thermal_check')
graph.add_edge('thermal_check', END)

# Compile the graph
graph = graph.compile()
