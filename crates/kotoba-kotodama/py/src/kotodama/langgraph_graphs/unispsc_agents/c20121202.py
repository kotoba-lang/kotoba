from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class RobotAxisState(TypedDict):
    part_id: str
    specs: dict
    validation_log: Annotated[List[str], operator.add]
    is_approved: bool

def validate_specs(state: RobotAxisState) -> RobotAxisState:
    torque = state['specs'].get('torque_rating', 0)
    if torque > 500:
        return {'validation_log': ['Torque exceeds safety threshold, triggering manual engineering review.'], 'is_approved': False}
    return {'validation_log': ['Technical specs validated successfully.'], 'is_approved': True}

def process_procurement(state: RobotAxisState) -> RobotAxisState:
    if state['is_approved']:
        return {'validation_log': ['Procurement workflow initiated for qualified component.']}
    return {'validation_log': ['Component failed validation, order halted.']}

graph = StateGraph(RobotAxisState)
graph.add_node('validate', validate_specs)
graph.add_node('procure', process_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'procure')
graph.add_edge('procure', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'part_id': "",
    'specs': {},
    'validation_log': [],
    'is_approved': False
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
