from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class ChemicalProcurementState(TypedDict):
    material_id: str
    purity: float
    safety_clearance: bool
    history: Annotated[list, operator.add]

def validate_composition(state: ChemicalProcurementState):
    # Simulate composition validation against safety protocols
    is_safe = state['purity'] >= 0.99
    return {'safety_clearance': is_safe, 'history': ['Validated composition']}

def route_procurement(state: ChemicalProcurementState):
    if state['safety_clearance']:
        return 'process_order'
    return 'flag_for_review'

def process_order(state: ChemicalProcurementState):
    return {'history': ['Order processing initialized']}

def flag_for_review(state: ChemicalProcurementState):
    return {'history': ['Flagged for secondary safety audit']}

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate', validate_composition)
graph.add_node('process_order', process_order)
graph.add_node('flag_for_review', flag_for_review)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_procurement)
graph.add_edge('process_order', END)
graph.add_edge('flag_for_review', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'safety_clearance': False,
    'history': []
}


class _DefaultsWrapper2605231330:
    """Pre-fills missing TypedDict fields before delegating to the compiled graph."""

    __slots__ = ("_inner", "_defaults")

    def __init__(self, inner, defaults):
        self._inner = inner
        self._defaults = defaults

    def _merge(self, input_state):
        if not isinstance(input_state, dict):
            return input_state
        merged = dict(self._defaults)
        merged.update(input_state)
        return merged

    def invoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.invoke(merged, **kwargs)
        return self._inner.invoke(merged, config=config, **kwargs)

    async def ainvoke(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return await self._inner.ainvoke(merged, **kwargs)
        return await self._inner.ainvoke(merged, config=config, **kwargs)

    def stream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            return self._inner.stream(merged, **kwargs)
        return self._inner.stream(merged, config=config, **kwargs)

    async def astream(self, input_state, config=None, **kwargs):
        merged = self._merge(input_state)
        if config is None:
            async for chunk in self._inner.astream(merged, **kwargs):
                yield chunk
            return
        async for chunk in self._inner.astream(merged, config=config, **kwargs):
            yield chunk

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)


graph = _DefaultsWrapper2605231330(graph, _DEFAULTS_2605231330)
