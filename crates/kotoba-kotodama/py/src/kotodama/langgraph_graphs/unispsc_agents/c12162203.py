from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_code: str
    purity_level: float
    hazard_check: bool
    validation_log: Annotated[Sequence[str], operator.add]

def validate_catalyst_purity(state: CatalystState):
    is_pure = state['purity_level'] >= 99.5
    return {'validation_log': [f'Purity check: {is_pure} (Level: {state['purity_level']}%)']}

def safety_compliance_check(state: CatalystState):
    is_safe = not state['hazard_check']
    return {'validation_log': [f'Safety check: {is_safe}']}

graph = StateGraph(CatalystState)
graph.add_node('purity_check', validate_catalyst_purity)
graph.add_node('safety_check', safety_compliance_check)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_code': "",
    'purity_level': 0.0,
    'hazard_check': False,
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
