from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class CrudeOilState(TypedDict):
    batch_id: str
    gravity: float
    sulfur: float
    status: str
    logs: Annotated[list[str], operator.add]

def validate_chemistry(state: CrudeOilState) -> CrudeOilState:
    if state['sulfur'] > 0.5:
        return {'status': 'REJECTED_SULFUR_TOO_HIGH', 'logs': ['Sulfur content exceeds threshold']}
    return {'status': 'VALIDATED', 'logs': ['Chemistry check passed']}

def check_compliance(state: CrudeOilState) -> CrudeOilState:
    if state['status'] != 'VALIDATED': return state
    return {'status': 'COMPLIANCE_CLEARED', 'logs': ['Sanctions screening passed']}

graph = StateGraph(CrudeOilState)
graph.add_node('chemistry', validate_chemistry)
graph.add_node('compliance', check_compliance)
graph.add_edge('chemistry', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('chemistry')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'batch_id': "",
    'gravity': 0.0,
    'sulfur': 0.0,
    'status': "",
    'logs': []
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
