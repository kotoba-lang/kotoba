from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CarbonFiberState(TypedDict):
    batch_id: str
    purity_level: float
    specs: dict
    validation_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: CarbonFiberState) -> dict:
    if state['purity_level'] < 0.99:
        return {'validation_log': ['Purity level below industrial standard requirement.']}
    return {'validation_log': ['Purity validation passed.']}

def structural_integrity_check(state: CarbonFiberState) -> dict:
    if state['specs'].get('tensile_strength_mpa', 0) < 3500:
        return {'validation_log': ['Tensile strength does not meet aerospace grade.']}
    return {'validation_log': ['Structural check passed.']}

def define_graph():
    workflow = StateGraph(CarbonFiberState)
    workflow.add_node('validate_purity', validate_purity)
    workflow.add_node('structural_integrity', structural_integrity_check)
    workflow.set_entry_point('validate_purity')
    workflow.add_edge('validate_purity', 'structural_integrity')
    workflow.add_edge('structural_integrity', END)
    return workflow.compile()

graph = define_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'purity_level': 0.0,
    'specs': {},
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
