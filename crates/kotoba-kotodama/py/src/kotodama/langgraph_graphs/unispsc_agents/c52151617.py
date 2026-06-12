from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_name: str
    quality_passed: bool
    compliance_docs: List[str]

def validate_food_safety(state: ProcurementState):
    # Simulate wood safety and coating validation
    state['quality_passed'] = 'food_safety_cert' in state['compliance_docs']
    return state

def check_dimensions(state: ProcurementState):
    # Specialized check for spoon geometry
    print('Verifying spoon dimensions against specs...')
    return state

graph = StateGraph(ProcurementState)
graph.add_node('safety_check', validate_food_safety)
graph.add_node('dimension_check', check_dimensions)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'item_name': "",
    'quality_passed': False,
    'compliance_docs': []
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
