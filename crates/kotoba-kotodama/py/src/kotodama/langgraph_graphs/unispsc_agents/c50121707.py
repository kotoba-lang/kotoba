from typing import TypedDict
from langgraph.graph import StateGraph, END
class SupplyState(TypedDict):
    product_id: str
    quality_passed: bool
    expiry_check: bool
def validate_quality(state: SupplyState):
    print(f'Validating quality for {state.get('product_id')}')
    return {'quality_passed': True}
def check_expiry(state: SupplyState):
    print('Checking shelf stability metadata...')
    return {'expiry_check': True}
graph = StateGraph(SupplyState)
graph.add_node('quality', validate_quality)
graph.add_node('expiry', check_expiry)
graph.set_entry_point('quality')
graph.add_edge('quality', 'expiry')
graph.add_edge('expiry', END)
graph = graph.compile()
