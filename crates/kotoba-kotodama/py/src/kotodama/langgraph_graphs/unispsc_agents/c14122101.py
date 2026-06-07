from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ThermalPaperState(TypedDict):
    paper_width: float
    roll_diameter: float
    archival_required: bool
    validation_logs: List[str]
    approved: bool

def validate_specs(state: ThermalPaperState) -> dict:
    logs = []
    if state['paper_width'] <= 0:
        logs.append('Invalid width')
    if state['roll_diameter'] > 200:
        logs.append('Diameter exceeds feeder capacity')
    return {'validation_logs': logs, 'approved': len(logs) == 0}

def update_inventory(state: ThermalPaperState) -> dict:
    return {'validation_logs': state['validation_logs'] + ['Inventory updated']}

graph = StateGraph(ThermalPaperState)
graph.add_node('validate', validate_specs)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'paper_width': 0.0,
    'roll_diameter': 0.0,
    'archival_required': False,
    'validation_logs': [],
    'approved': False
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
