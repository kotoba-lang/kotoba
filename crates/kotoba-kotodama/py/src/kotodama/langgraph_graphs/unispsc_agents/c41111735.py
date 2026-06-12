from typing import TypedDict
from langgraph.graph import StateGraph, END

class MicroscopeGraphState(TypedDict):
    stage_specs: dict
    validation_log: list
    is_compliant: bool

def validate_precision(state: MicroscopeGraphState):
    accuracy = state['stage_specs'].get('accuracy', 1.0)
    valid = accuracy <= 0.5
    return {'validation_log': [f"Precision check: {'Pass' if valid else 'Fail'}"], 'is_compliant': valid}

def check_dual_use(state: MicroscopeGraphState):
    return {'validation_log': state['validation_log'] + ['Export control check: Flagged for high-precision optics']}

graph = StateGraph(MicroscopeGraphState)
graph.add_node("precision_check", validate_precision)
graph.add_node("export_check", check_dual_use)
graph.set_entry_point("precision_check")
graph.add_edge("precision_check", "export_check")
graph.add_edge("export_check", END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'stage_specs': {},
    'validation_log': [],
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
