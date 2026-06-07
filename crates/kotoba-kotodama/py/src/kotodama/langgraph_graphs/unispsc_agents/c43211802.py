from typing import TypedDict
from langgraph.graph import StateGraph, END

class MousePadState(TypedDict):
    spec_data: dict
    validation_result: bool
    error_log: list

def validate_dimensions(state: MousePadState):
    dims = state['spec_data'].get('dimensions', {})
    valid = dims.get('width', 0) > 0 and dims.get('height', 0) > 0
    return {'validation_result': valid, 'error_log': [] if valid else ['Invalid dimensions']}

def check_compliance(state: MousePadState):
    compliant = state['spec_data'].get('rohs_compliant', False)
    return {'validation_result': state['validation_result'] and compliant}

workflow = StateGraph(MousePadState)
workflow.add_node('validate_dim', validate_dimensions)
workflow.add_node('check_comp', check_compliance)
workflow.add_edge('validate_dim', 'check_comp')
workflow.add_edge('check_comp', END)
workflow.set_entry_point('validate_dim')
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_data': {},
    'validation_result': False,
    'error_log': []
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
