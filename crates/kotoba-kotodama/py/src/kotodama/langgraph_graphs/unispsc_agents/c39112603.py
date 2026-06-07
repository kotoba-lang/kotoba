from typing import TypedDict
from langgraph.graph import StateGraph, END

class LanternState(TypedDict):
    fuel_type: str
    safety_check_passed: bool
    compliance_docs: list

def validate_fuel_compliance(state: LanternState):
    allowed = ['kerosene', 'propane', 'natural_gas', 'butane']
    return {'safety_check_passed': state['fuel_type'] in allowed}

def process_procurement(state: LanternState):
    return {'compliance_docs': ['ISO_safety_cert', 'fire_hazard_test']}

graph = StateGraph(LanternState)
graph.add_node('validate_fuel', validate_fuel_compliance)
graph.add_node('compile_docs', process_procurement)
graph.add_edge('validate_fuel', 'compile_docs')
graph.add_edge('compile_docs', END)
graph.set_entry_point('validate_fuel')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'fuel_type': "",
    'safety_check_passed': False,
    'compliance_docs': []
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
