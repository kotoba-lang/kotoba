from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class WaterTreatmentState(TypedDict):
    supply_type: str
    compliance_docs: List[str]
    risk_score: float

def validate_compliance(state: WaterTreatmentState):
    print('Validating chemical compliance...')
    return {'risk_score': 0.2}

def route_procurement(state: WaterTreatmentState):
    if 'hazardous' in state['supply_type']:
        return 'hazardous_handling'
    return 'standard_procurement'

graph = StateGraph(WaterTreatmentState)
graph.add_node('validate', validate_compliance)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
