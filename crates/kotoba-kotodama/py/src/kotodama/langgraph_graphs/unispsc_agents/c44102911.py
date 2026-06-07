from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OfficeSupplyState(TypedDict):
    product_id: str
    specifications: dict
    validation_passed: bool
    compliance_report: str

def validate_safety_data(state: OfficeSupplyState):
    sds_info = state['specifications'].get('sds_available', False)
    return {'validation_passed': sds_info, 'compliance_report': 'SDS Checked' if sds_info else 'SDS Missing'}

def audit_specifications(state: OfficeSupplyState):
    is_lint_free = state['specifications'].get('is_lint_free', True)
    return {'validation_passed': state['validation_passed'] and is_lint_free}

graph = StateGraph(OfficeSupplyState)
graph.add_node('validate_sds', validate_safety_data)
graph.add_node('check_specs', audit_specifications)
graph.set_entry_point('validate_sds')
graph.add_edge('validate_sds', 'check_specs')
graph.add_edge('check_specs', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'product_id': "",
    'specifications': {},
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
