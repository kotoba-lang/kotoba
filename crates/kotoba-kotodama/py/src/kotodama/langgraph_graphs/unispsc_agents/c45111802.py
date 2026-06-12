from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MountState(TypedDict):
    vesa_compliance: bool
    max_load: float
    inspection_status: str

def validate_specs(state: MountState):
    if state['vesa_compliance'] and state['max_load'] > 0:
        return {'inspection_status': 'PASSED'}
    return {'inspection_status': 'FAILED'}

def deploy_mount(state: MountState):
    print(f'Mount workflow finalized: {state["inspection_status"]}')
    return state

builder = StateGraph(MountState)
builder.add_node('validate', validate_specs)
builder.add_node('deploy', deploy_mount)
builder.set_entry_point('validate')
builder.add_edge('validate', 'deploy')
builder.add_edge('deploy', END)
graph = builder.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'vesa_compliance': False,
    'max_load': 0.0,
    'inspection_status': ""
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
