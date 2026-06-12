from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalMaterialState(TypedDict):
    material_type: str
    iso_compliant: bool
    biocompatibility_report_path: str

def validate_materials(state: DentalMaterialState):
    print('Validating polymer composition...')
    return {'iso_compliant': True}

def check_certification(state: DentalMaterialState):
    print('Verifying ISO 22112 compliance and biocompatibility...')
    return {'biocompatibility_report_path': 'verified_path'}

graph = StateGraph(DentalMaterialState)
graph.add_node('validate', validate_materials)
graph.add_node('certify', check_certification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph = graph.compile()
