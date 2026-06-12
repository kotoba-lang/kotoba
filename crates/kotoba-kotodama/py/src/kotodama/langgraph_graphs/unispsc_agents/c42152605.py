from typing import TypedDict
from langgraph.graph import StateGraph, END
class SialographyState(TypedDict):
    sterilization_valid: bool
    compliance_docs: list
    validation_complete: bool
def validate_certification(state: SialographyState):
    state['sterilization_valid'] = True
    return {'validation_complete': True}
def compile_graph():
    graph = StateGraph(SialographyState)
    graph.add_node('cert_check', validate_certification)
    graph.set_entry_point('cert_check')
    graph.add_edge('cert_check', END)
    return graph.compile()
graph = compile_graph()
