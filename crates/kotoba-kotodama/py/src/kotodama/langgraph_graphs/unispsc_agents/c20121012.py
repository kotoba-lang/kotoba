from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotComponentState(TypedDict):
    component_id: str
    spec_sheet: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_component(state: RobotComponentState):
    logs = state.get('validation_logs', [])
    logs.append(f'Validating component {state['component_id']} for industrial standards.')
    return {'validation_logs': logs, 'is_compliant': True}

def generate_procurement_report(state: RobotComponentState):
    return {'validation_logs': state['validation_logs'] + ['Generating final procurement report.']}

graph = StateGraph(RobotComponentState)
graph.add_node('validate', validate_component)
graph.add_node('report', generate_procurement_report)
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'component_id': "",
    'spec_sheet': {},
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
