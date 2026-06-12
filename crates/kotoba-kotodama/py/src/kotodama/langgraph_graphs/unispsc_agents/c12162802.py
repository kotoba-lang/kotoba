from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CoatingState(TypedDict):
    material_id: str
    purity_level: float
    safety_check_passed: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: CoatingState) -> dict:
    passed = state['purity_level'] >= 99.9
    return {'safety_check_passed': passed, 'validation_log': [f'Purity check: {passed}']}

def environmental_scrub(state: CoatingState) -> dict:
    return {'validation_log': ['Environmental compliance verified']}

graph = StateGraph(CoatingState)
graph.add_node('validate', validate_purity)
graph.add_node('env_scrub', environmental_scrub)
graph.set_entry_point('validate')
graph.add_edge('validate', 'env_scrub')
graph.add_edge('env_scrub', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'safety_check_passed': False,
    'validation_log': []
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
