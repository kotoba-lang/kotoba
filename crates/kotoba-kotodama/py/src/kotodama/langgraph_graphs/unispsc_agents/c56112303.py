from typing import TypedDict
from langgraph.graph import StateGraph, END

class SeatPivotState(TypedDict):
    part_number: str
    material_certified: bool
    torque_check_passed: bool

def validate_materials(state: SeatPivotState):
    print(f'Checking material certification for {state['part_number']}')
    return {'material_certified': True}

def perform_torque_test(state: SeatPivotState):
    print('Executing mechanical torque and rotation testing...')
    return {'torque_check_passed': True}

graph = StateGraph(SeatPivotState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('torque_test', perform_torque_test)
graph.add_edge('validate_materials', 'torque_test')
graph.add_edge('torque_test', END)
graph.set_entry_point('validate_materials')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'material_certified': False,
    'torque_check_passed': False
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
