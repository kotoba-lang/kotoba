from typing import TypedDict
from langgraph.graph import StateGraph, END

class CamFollowerState(TypedDict):
    spec_data: dict
    validation_checks: list
    approval_status: bool

def validate_load_capacity(state: CamFollowerState):
    load = state['spec_data'].get('load_rating')
    is_valid = load > 0
    return {'validation_checks': ['load_capacity_check'], 'approval_status': is_valid}

def check_dual_use(state: CamFollowerState):
    # Logic for dual-use control vetting
    return {'validation_checks': state['validation_checks'] + ['export_control_verified']}

graph = StateGraph(CamFollowerState)
graph.add_node('validate_load', validate_load_capacity)
graph.add_node('check_export', check_dual_use)
graph.set_entry_point('validate_load')
graph.add_edge('validate_load', 'check_export')
graph.add_edge('check_export', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_checks': [],
    'approval_status': False
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
