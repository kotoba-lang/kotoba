from typing import TypedDict
from langgraph.graph import StateGraph, END

class TapeDriveState(TypedDict):
    model_number: str
    lto_generation: str
    validation_status: bool

def validate_tape_spec(state: TapeDriveState) -> TapeDriveState:
    # Logic to verify LTO compatibility and drive firmware integrity
    state['validation_status'] = 'LTO' in state['lto_generation']
    return state

def secure_config_check(state: TapeDriveState) -> TapeDriveState:
    # Logic for restricted export/sanctions risk checks
    print(f'Checking {state['model_number']} for export compliance...')
    return state

graph = StateGraph(TapeDriveState)
graph.add_node('validate_spec', validate_tape_spec)
graph.add_node('compliance_check', secure_config_check)
graph.set_entry_point('validate_spec')
graph.add_edge('validate_spec', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'model_number': "",
    'lto_generation': "",
    'validation_status': False
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
