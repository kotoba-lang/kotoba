from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class DentalSupplyState(TypedDict):
    product_specs: dict
    compliance_report: str
    approved: bool

def validate_dimensions(state: DentalSupplyState):
    # Simulate validation logic for headrest cover dimensions
    fit = state['product_specs'].get('dimensions', 0) > 0
    return {'compliance_report': 'Dimensions verified' if fit else 'Dimension mismatch'}

def check_certification(state: DentalSupplyState):
    # Verify ISO 13485 or similar health compliance
    is_certified = state['product_specs'].get('certified', False)
    return {'approved': is_certified}

graph = StateGraph(DentalSupplyState)
graph.add_node('validate_dims', validate_dimensions)
graph.add_node('check_cert', check_certification)
graph.add_edge('validate_dims', 'check_cert')
graph.add_edge('check_cert', END)
graph.set_entry_point('validate_dims')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_specs': {},
    'compliance_report': "",
    'approved': False
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
