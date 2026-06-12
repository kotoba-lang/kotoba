from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
import operator

class ActuatorState(TypedDict):
    part_number: str
    torque_nm: float
    voltage_v: float
    validation_log: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_actuator_specs(state: ActuatorState):
    log = []
    if state['torque_nm'] <= 0:
        log.append('Invalid torque: must be positive')
    if state['voltage_v'] < 12 or state['voltage_v'] > 48:
        log.append('Voltage outside industrial standard range 12-48V')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

def process_procurement(state: ActuatorState):
    print(f'Processing procurement for {state['part_number']}')
    return state

graph = StateGraph(ActuatorState)
graph.add_node('validate', validate_actuator_specs)
graph.add_node('process', process_procurement)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_number': "",
    'torque_nm': 0.0,
    'voltage_v': 0.0,
    'validation_log': [],
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
