from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    spec: dict
    validation_results: Annotated[list, operator.add]
    status: str

def validate_torque(state: GearState):
    torque = state['spec'].get('rated_torque_nm', 0)
    valid = torque > 0
    return {'validation_results': [f'Torque check: {valid}']}

def check_backlash(state: GearState):
    backlash = state['spec'].get('backlash_arcmin', 10)
    valid = backlash <= 5
    return {'validation_results': [f'Backlash precision: {valid}']}

def assemble_status(state: GearState):
    return {'status': 'Validated' if all('True' in r for r in state['validation_results']) else 'Failed'}

graph = StateGraph(GearState)
graph.add_node('torque', validate_torque)
graph.add_node('backlash', check_backlash)
graph.add_node('status', assemble_status)
graph.set_entry_point('torque')
graph.add_edge('torque', 'backlash')
graph.add_edge('backlash', 'status')
graph.add_edge('status', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec': {},
    'validation_results': [],
    'status': ""
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
