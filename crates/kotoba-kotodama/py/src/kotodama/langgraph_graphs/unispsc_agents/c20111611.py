from typing import TypedDict, Annotated; from langgraph.graph import StateGraph, END; import operator

class ToolSteelState(TypedDict):
    material_spec: str
    inspection_results: Annotated[list[str], operator.add]
    is_compliant: bool

def validate_material(state: ToolSteelState) -> ToolSteelState:
    if 'steel_grade_compliant' in state.get('material_spec', ''):
        return {'inspection_results': ['Material passed analysis']}
    return {'inspection_results': ['Material failed analysis']}

def perform_inspection(state: ToolSteelState) -> ToolSteelState:
    if len(state['inspection_results']) > 0:
        return {'is_compliant': True}
    return {'is_compliant': False}

graph = StateGraph(ToolSteelState)
graph.add_node('validate', validate_material)
graph.add_node('inspect', perform_inspection)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()
