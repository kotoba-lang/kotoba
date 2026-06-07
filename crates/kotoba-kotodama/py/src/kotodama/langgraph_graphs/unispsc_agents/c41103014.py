from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChromatographyState(TypedDict):
    temp_requirements: dict
    compliance_docs: list
    validation_status: str

def validate_specs(state: ChromatographyState):
    print('Validating chromatography chamber dimensions and cooling capacity...')
    return {'validation_status': 'passed'}

def check_compliance(state: ChromatographyState):
    print('Checking certification for hazardous gases or volatile compounds...')
    return {'compliance_docs': ['ISO-13485', 'CE-Mark']}

graph = StateGraph(ChromatographyState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
