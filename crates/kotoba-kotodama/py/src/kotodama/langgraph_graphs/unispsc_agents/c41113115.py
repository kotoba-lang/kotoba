from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class RadonProcurementState(TypedDict):
    sensor_id: str
    calibration_status: bool
    safety_compliance: bool
    inspection_report: str

class WorkflowManager:
    def validate_calibration(self, state: RadonProcurementState):
        print(f'Validating calibration for {state['sensor_id']}')
        return {'calibration_status': True}

    def check_nrc_regs(self, state: RadonProcurementState):
        print('Verifying nuclear regulatory compliance')
        return {'safety_compliance': True}

manager = WorkflowManager()
graph = StateGraph(RadonProcurementState)
graph.add_node('calibrate', manager.validate_calibration)
graph.add_node('safety_check', manager.check_nrc_regs)
graph.set_entry_point('calibrate')
graph.add_edge('calibrate', 'safety_check')
graph.add_edge('safety_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'sensor_id': "",
    'calibration_status': False,
    'safety_compliance': False,
    'inspection_report': ""
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
