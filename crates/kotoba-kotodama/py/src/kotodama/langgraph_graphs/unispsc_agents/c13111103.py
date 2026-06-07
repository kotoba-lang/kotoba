from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class CrudeState(TypedDict):
    api_gravity: float
    sulfur_content: float
    origin: str
    validation_passed: bool
    log: Annotated[list, operator.add]

def validate_quality(state: CrudeState) -> CrudeState:
    passed = state['api_gravity'] > 20 and state['sulfur_content'] < 0.5
    return {'validation_passed': passed, 'log': [f'Quality check: {passed}']}

def compliance_check(state: CrudeState) -> CrudeState:
    is_safe = state['origin'] not in ['restricted_zone_A', 'restricted_zone_B']
    return {'validation_passed': is_safe and state['validation_passed'], 'log': [f'Compliance check: {is_safe}']}

graph = StateGraph(CrudeState)
graph.add_node('quality', validate_quality)
graph.add_node('compliance', compliance_check)
graph.add_edge('quality', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('quality')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'api_gravity': 0.0,
    'sulfur_content': 0.0,
    'origin': "",
    'validation_passed': False,
    'log': []
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
