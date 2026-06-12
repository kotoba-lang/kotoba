from typing import TypedDict
from langgraph.graph import StateGraph, END

class ConstructionState(TypedDict):
    site_id: str
    geotech_report: dict
    approved: bool

def validate_geo_report(state: ConstructionState):
    report = state.get('geotech_report', {})
    is_valid = report.get('compaction_pct', 0) >= 95
    return {'approved': is_valid}

def deploy_workfow(state: ConstructionState):
    print(f'Proceeding with slope construction for site {state.get('site_id')}')
    return state

graph = StateGraph(ConstructionState)
graph.add_node('validate', validate_geo_report)
graph.add_node('deploy', deploy_workfow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
