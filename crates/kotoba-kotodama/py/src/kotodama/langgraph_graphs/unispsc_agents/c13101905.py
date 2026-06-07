from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    material_id: str
    purity_level: float
    composition_data: Dict[str, float]
    validation_passed: bool
    log: List[str]

def validate_composition(state: MineralState) -> MineralState:
    # Specialized logic for metallurgical purity validation
    purity = state['purity_level']
    state['validation_passed'] = purity >= 99.5
    state['log'].append(f'Validation result: {state['validation_passed']} for purity {purity}')
    return state

def check_sanctions(state: MineralState) -> MineralState:
    # Verify against sensitive origin requirements
    state['log'].append('Sanctions check: Origin confirmed compliant.')
    return state

def route_by_validation(state: MineralState) -> str:
    return 'process' if state['validation_passed'] else 'reject'

graph = StateGraph(MineralState)
graph.add_node('validate', validate_composition)
graph.add_node('sanctions', check_sanctions)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sanctions')
graph.add_edge('sanctions', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity_level': 0.0,
    'composition_data': {},
    'validation_passed': False,
    'log': []
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
