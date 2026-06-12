from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    part_number: str
    specs: dict
    validation_log: List[str]
    is_compliant: bool

def validate_specs(state: BearingState) -> BearingState:
    specs = state.get('specs', {})
    log = []
    if 'load_rating_kn' not in specs: log.append('Missing Load Rating')
    if 'material_grade' not in specs: log.append('Missing Material Grade')
    return {**state, 'validation_log': log, 'is_compliant': len(log) == 0}

def route_by_compliance(state: BearingState) -> str:
    return 'process' if state['is_compliant'] else 'flag'

def process_bearing(state: BearingState) -> BearingState:
    return {**state, 'validation_log': state['validation_log'] + ['Processing validated bearing']}

def flag_error(state: BearingState) -> BearingState:
    return {**state, 'validation_log': state['validation_log'] + ['Flagged for manual review']}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_specs)
graph.add_node('process', process_bearing)
graph.add_node('flag', flag_error)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph.add_edge('flag', END)
graph = graph.compile()
