from typing import TypedDict
from langgraph.graph import StateGraph, END

class PurificationState(TypedDict):
    sample_id: str
    purity_check_passed: bool
    storage_temp_valid: bool

def validate_sample_integrity(state: PurificationState) -> PurificationState:
    print(f'Validating viral DNA integrity for {state['sample_id']}')
    state['purity_check_passed'] = True
    return state

def check_cold_chain(state: PurificationState) -> PurificationState:
    print('Verifying cold chain logistics compliance')
    state['storage_temp_valid'] = True
    return state

graph = StateGraph(PurificationState)
graph.add_node('validate', validate_sample_integrity)
graph.add_node('cold_chain', check_cold_chain)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'sample_id': "",
    'purity_check_passed': False,
    'storage_temp_valid': False
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
