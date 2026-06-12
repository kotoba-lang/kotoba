from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MicrofluidicState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[Sequence[str], add_messages]
    is_compliant: bool

def validate_specs(state: MicrofluidicState):
    # Simulated complex validation logic for microfluidic device specs
    reqs = state.get('spec_requirements', {})
    compliant = reqs.get('flow_accuracy') == 'high' and reqs.get('sterilized') == True
    return {'is_compliant': compliant, 'validation_logs': ['Validation complete. Compliance: ' + str(compliant)]}

def process_procurement(state: MicrofluidicState):
    if state['is_compliant']:
        return 'approve'
    return 'flag_for_review'

graph = StateGraph(MicrofluidicState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
