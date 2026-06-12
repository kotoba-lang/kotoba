from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class MotorProcurementState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[list[str], operator.add]
    is_compliant: bool

def validate_specs(state: MotorProcurementState):
    specs = state['spec_requirements']
    logs = []
    compliant = True
    if specs.get('torque_rating_nm', 0) < 0.1:
        logs.append('Torque insufficient for heavy industrial application.')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def check_dual_use(state: MotorProcurementState):
    logs = ['Checking dual-use export compliance.']
    return {'validation_logs': logs}

workflow = StateGraph(MotorProcurementState)
workflow.add_node('validate', validate_specs)
workflow.add_node('export_check', check_dual_use)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'export_check')
workflow.add_edge('export_check', END)
graph = workflow.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_logs': [],
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
