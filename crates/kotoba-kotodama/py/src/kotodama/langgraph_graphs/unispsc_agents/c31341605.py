from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    material_spec: str
    bonding_strength: float
    inspection_passed: bool
    history: List[str]

def validate_materials(state: ProcurementState):
    passed = state['material_spec'] in ['ASTM-A514', 'JIS-SM490']
    return {'inspection_passed': passed, 'history': ['Material validated']}

def check_bonding(state: ProcurementState):
    passed = state['bonding_strength'] >= 450.0
    return {'inspection_passed': state['inspection_passed'] and passed, 'history': state['history'] + ['Bonding tested']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_materials)
graph.add_node('bonding', check_bonding)
graph.set_entry_point('validate')
graph.add_edge('validate', 'bonding')
graph.add_edge('bonding', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_spec': "",
    'bonding_strength': 0.0,
    'inspection_passed': False,
    'history': []
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
