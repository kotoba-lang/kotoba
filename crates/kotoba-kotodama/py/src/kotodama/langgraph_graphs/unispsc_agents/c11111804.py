from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    grade: str
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_material(state: SteelProcurementState) -> SteelProcurementState:
    specs = state.get('specs', {})
    log = []
    compliant = True
    if 'tensile_strength' not in specs:
        log.append('Missing tensile strength specification')
        compliant = False
    return {**state, 'is_compliant': compliant, 'validation_log': log}

def process_procurement(state: SteelProcurementState) -> SteelProcurementState:
    return {**state, 'validation_log': state['validation_log'] + ['Processing order through mill']}

graph = StateGraph(SteelProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('process', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
