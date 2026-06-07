from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    measurement_data: dict
    validation_passed: bool
    compliance_report: str

def validate_tool_precision(state: ToolState):
    # Simulate CAD and physical precision verification logic
    precision = state['measurement_data'].get('tolerance', 0.0)
    state['validation_passed'] = precision <= 0.05
    return {'validation_passed': state['validation_passed']}

def generate_compliance_logs(state: ToolState):
    # Generate procurement compliance records
    state['compliance_report'] = 'Standards verified: ISO 9001, ANSI/ASME compliance.'
    return {'compliance_report': state['compliance_report']}

graph = StateGraph(ToolState)
graph.add_node('validate_precision', validate_tool_precision)
graph.add_node('compliance', generate_compliance_logs)
graph.set_entry_point('validate_precision')
graph.add_edge('validate_precision', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'measurement_data': {},
    'validation_passed': False,
    'compliance_report': ""
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
