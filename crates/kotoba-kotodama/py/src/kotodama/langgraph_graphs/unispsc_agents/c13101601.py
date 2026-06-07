from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GasSupplyState(TypedDict):
    commodity_code: str
    pressure: float
    purity_level: float
    compliance_checks: List[str]
    status: str

def validate_pressure(state: GasSupplyState):
    is_valid = state['pressure'] > 500
    return {'status': 'pressure_ok' if is_valid else 'pressure_fail'}

def check_purity(state: GasSupplyState):
    purity_ok = state['purity_level'] >= 98.5
    return {'compliance_checks': ['purity_standard'] if purity_ok else []}

graph = StateGraph(GasSupplyState)
graph.add_node('validate_pressure', validate_pressure)
graph.add_node('check_purity', check_purity)
graph.add_edge('validate_pressure', 'check_purity')
graph.add_edge('check_purity', END)
graph.set_entry_point('validate_pressure')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'commodity_code': "",
    'pressure': 0.0,
    'purity_level': 0.0,
    'compliance_checks': [],
    'status': ""
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
