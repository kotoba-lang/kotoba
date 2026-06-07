from typing import TypedDict
from langgraph.graph import StateGraph, END

class AnatomyChartState(TypedDict):
    chart_id: str
    is_medically_accurate: bool
    physical_condition: str
    approved: bool

def validate_accuracy(state: AnatomyChartState):
    return {'is_medically_accurate': True if state.get('chart_id') else False}

def check_quality(state: AnatomyChartState):
    condition = state.get('physical_condition', '')
    return {'approved': 'torn' not in condition.lower()}

graph = StateGraph(AnatomyChartState)
graph.add_node('validate', validate_accuracy)
graph.add_node('quality_check', check_quality)
graph.add_edge('validate', 'quality_check')
graph.add_edge('quality_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
