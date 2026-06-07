from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MineralState(TypedDict):
    raw_input: dict
    compliance_validated: bool
    purity_score: float
    messages: Annotated[Sequence[str], add_messages]

def validate_compliance(state: MineralState):
    # Simulated compliance logic for raw mineral procurement
    origin = state['raw_input'].get('origin', 'unknown')
    is_compliant = origin not in ['sanctioned_region_x']
    return {'compliance_validated': is_compliant, 'messages': ['Compliance check completed']}

def process_purity(state: MineralState):
    # Simulated technical analysis logic
    purity = state['raw_input'].get('purity_value', 0.0)
    return {'purity_score': purity, 'messages': ['Purity analysis finalized']}

graph = StateGraph(MineralState)
graph.add_node('compliance', validate_compliance)
graph.add_node('analysis', process_purity)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'analysis')
graph.add_edge('analysis', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_input': {},
    'compliance_validated': False,
    'purity_score': 0.0,
    'messages': []
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
