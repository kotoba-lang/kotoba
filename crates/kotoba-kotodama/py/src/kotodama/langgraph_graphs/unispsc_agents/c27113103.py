from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class FidState(TypedDict):
    fid_type: str
    material: str
    is_compliant: bool
    validation_log: List[str]

def validate_fid_specs(state: FidState):
    log = ['Initiating tool specification check...']
    compliant = True
    if not state.get('material'):
        log.append('Material specification missing.')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def final_report(state: FidState):
    return {'validation_log': state['validation_log'] + ['Processing complete.']}

graph = StateGraph(FidState)
graph.add_node('validate', validate_fid_specs)
graph.add_node('report', final_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
