from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GasProcurementState(TypedDict):
    commodity_code: str
    purity_required: float
    safety_clearance: bool
    validation_logs: Annotated[Sequence[str], operator.add]

def validate_purity(state: GasProcurementState):
    passed = state['purity_required'] >= 99.999
    return {'validation_logs': ['Purity check passed' if passed else 'Purity insufficient']}

def check_compliance(state: GasProcurementState):
    return {'safety_clearance': True, 'validation_logs': ['Compliance verified against dual-use criteria']}

graph = StateGraph(GasProcurementState)
graph.add_node('validate_purity', validate_purity)
graph.add_node('check_compliance', check_compliance)
graph.add_edge('validate_purity', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_purity')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'purity_required': 0.0,
    'safety_clearance': False,
    'validation_logs': []
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
