from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CarbonIngestState(TypedDict):
    raw_data: dict
    purity_validated: bool
    compliance_cleared: bool
    analysis_logs: Annotated[List[str], add_messages]

def validate_purity(state: CarbonIngestState):
    purity = state['raw_data'].get('purity', 0)
    is_valid = purity >= 99.999
    return {'purity_validated': is_valid, 'analysis_logs': [f'Purity check: {purity}% - Validated: {is_valid}']}

def check_compliance(state: CarbonIngestState):
    is_compliant = state.get('purity_validated', False)
    return {'compliance_cleared': is_compliant, 'analysis_logs': [f'Export compliance cleared: {is_compliant}']}

graph = StateGraph(CarbonIngestState)
graph.add_node('purity_check', validate_purity)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('purity_check')
graph.add_edge('purity_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'raw_data': {},
    'purity_validated': False,
    'compliance_cleared': False,
    'analysis_logs': []
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
