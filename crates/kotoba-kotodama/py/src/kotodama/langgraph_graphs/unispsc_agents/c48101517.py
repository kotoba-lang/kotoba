from typing import TypedDict
from langgraph.graph import StateGraph, END

class KitchenEquipmentState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: KitchenEquipmentState):
    specs = state.get('spec_data', {})
    required = ['Voltage', 'NSF_Certified']
    compliance = all(k in specs for k in required)
    return {'is_compliant': compliance, 'validation_log': ['Specs checked against commercial standards']}

def deploy_procurement(state: KitchenEquipmentState):
    if state['is_compliant']:
        return {'validation_log': state['validation_log'] + ['Procurement approved']}
    return {'validation_log': state['validation_log'] + ['Procurement flagged for review']}

graph = StateGraph(KitchenEquipmentState)
graph.add_node('validate', validate_specs)
graph.add_node('deploy', deploy_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
