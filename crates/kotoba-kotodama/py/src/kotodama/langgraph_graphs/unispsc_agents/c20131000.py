from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MiningMachineryState(TypedDict):
    part_specs: dict
    validation_log: list[str]
    approved: bool

def validate_component_specs(state: MiningMachineryState):
    specs = state.get('part_specs', {})
    log = []
    if specs.get('material_grade') == 'certified':
        log.append('Material grade validated.')
    else:
        log.append('Material grade failed validation.')
    return {'validation_log': log}

def decision_node(state: MiningMachineryState):
    if 'Material grade validated.' in state.get('validation_log', []):
        return {'approved': True}
    return {'approved': False}

graph = StateGraph(MiningMachineryState)
graph.add_node('validate', validate_component_specs)
graph.add_node('decide', decision_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'decide')
graph.add_edge('decide', END)
graph = graph.compile()
