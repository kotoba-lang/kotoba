from typing import TypedDict
from langgraph.graph import StateGraph, END

class OxidizerState(TypedDict):
    cas_number: str
    purity: float
    hazard_check_passed: bool

def validate_safety_data(state: OxidizerState):
    # Simulate regulatory validation for dangerous goods
    state['hazard_check_passed'] = state['cas_number'] is not None
    return state

def compliance_check(state: OxidizerState):
    print(f'Checking compliance for CAS: {state['cas_number']}')
    return {'hazard_check_passed': True}

graph = StateGraph(OxidizerState)
graph.add_node('validation', validate_safety_data)
graph.add_node('compliance', compliance_check)
graph.add_edge('validation', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validation')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'cas_number': "",
    'purity': 0.0,
    'hazard_check_passed': False
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
