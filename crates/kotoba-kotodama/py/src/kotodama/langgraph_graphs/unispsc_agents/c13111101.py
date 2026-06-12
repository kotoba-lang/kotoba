from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    raw_data: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_purity(state: MineralState) -> dict:
    purity = state['raw_data'].get('purity_percentage', 0)
    if purity >= 95.0:
        return {'validation_logs': ['Purity check passed'], 'is_compliant': True}
    return {'validation_logs': ['Purity check failed'], 'is_compliant': False}

def process_origin(state: MineralState) -> dict:
    return {'validation_logs': ['Origin verification completed']}

workflow = StateGraph(MineralState)
workflow.add_node('validate', validate_purity)
workflow.add_node('verify_origin', process_origin)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'verify_origin')
workflow.add_edge('verify_origin', END)

graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_data': {},
    'validation_logs': [],
    'is_compliant': False
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
