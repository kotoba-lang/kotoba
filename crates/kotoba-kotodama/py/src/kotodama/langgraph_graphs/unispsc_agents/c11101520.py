from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralIngestState(TypedDict):
    raw_data: dict
    purity_validated: bool
    compliance_tags: List[str]
    log: List[str]

def validate_chemical_purity(state: MineralIngestState) -> MineralIngestState:
    purity = state['raw_data'].get('purity', 0)
    state['purity_validated'] = purity >= 99.5
    state['log'].append(f'Purity check: {purity}%')
    return state

def check_sanctions(state: MineralIngestState) -> MineralIngestState:
    origin = state['raw_data'].get('origin', 'unknown')
    if origin in ['restricted_zone_a', 'restricted_zone_b']:
        state['compliance_tags'].append('sanctions-sensitive')
    return state

def compile_graph():
    builder = StateGraph(MineralIngestState)
    builder.add_node('validate', validate_chemical_purity)
    builder.add_node('compliance', check_sanctions)
    builder.set_entry_point('validate')
    builder.add_edge('validate', 'compliance')
    builder.add_edge('compliance', END)
    return builder.compile()

graph = compile_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_data': {},
    'purity_validated': False,
    'compliance_tags': [],
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
