from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class CarbonFiberState(TypedDict):
    fiber_id: str
    spec_data: dict
    validation_logs: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_fiber_specs(state: CarbonFiberState):
    specs = state['spec_data']
    logs = []
    compliant = True
    if specs.get('tensile_strength_mpa', 0) < 3000:
        logs.append('Insufficient tensile strength for industrial grade.')
        compliant = False
    return {'validation_logs': logs, 'is_compliant': compliant}

def check_dual_use_risk(state: CarbonFiberState):
    # Dual-use screening logic
    logs = ['Screening for export control regulations.']
    return {'validation_logs': logs}

graph = StateGraph(CarbonFiberState)
graph.add_node('validate', validate_fiber_specs)
graph.add_node('risk_check', check_dual_use_risk)
graph.set_entry_point('validate')
graph.add_edge('validate', 'risk_check')
graph.add_edge('risk_check', END)

graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'fiber_id': "",
    'spec_data': {},
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
