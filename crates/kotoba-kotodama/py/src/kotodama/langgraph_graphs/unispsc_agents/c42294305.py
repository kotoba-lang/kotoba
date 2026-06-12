from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class BiopsyUnitState(TypedDict):
    device_id: str
    compliance_passed: bool
    validation_logs: List[str]
def validate_medical_compliance(state: BiopsyUnitState):
    state['validation_logs'].append('Checking ISO 13485 standards...')
    state['compliance_passed'] = True
    return state
def check_vacuum_specs(state: BiopsyUnitState):
    state['validation_logs'].append('Verifying vacuum pressure calibration...')
    return state
workflow = StateGraph(BiopsyUnitState)
workflow.add_node('compliance', validate_medical_compliance)
workflow.add_node('vacuum_check', check_vacuum_specs)
workflow.set_entry_point('compliance')
workflow.add_edge('compliance', 'vacuum_check')
workflow.add_edge('vacuum_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'device_id': "",
    'compliance_passed': False,
    'validation_logs': []
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
