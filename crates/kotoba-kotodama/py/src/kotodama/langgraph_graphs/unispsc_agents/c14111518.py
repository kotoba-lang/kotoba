from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class PaperState(TypedDict):
    spec_requirements: dict
    validation_logs: Annotated[List[str], add_messages]
    status: str

def validate_gsm(state: PaperState) -> PaperState:
    gsm = state['spec_requirements'].get('gsm_weight', 0)
    if 60 <= gsm <= 120:
        state['validation_logs'].append(f'GSM {gsm} is within standard range.')
    else:
        state['validation_logs'].append(f'GSM {gsm} warning: outside standard range.')
    return state

def check_certification(state: PaperState) -> PaperState:
    cert = state['spec_requirements'].get('sustainablity_certification')
    if cert in ['FSC', 'PEFC']:
        state['status'] = 'COMPLIANT'
    else:
        state['status'] = 'PENDING_REVIEW'
    return state

graph = StateGraph(PaperState)
graph.add_node('validate_gsm', validate_gsm)
graph.add_node('check_cert', check_certification)
graph.set_entry_point('validate_gsm')
graph.add_edge('validate_gsm', 'check_cert')
graph.add_edge('check_cert', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'spec_requirements': {},
    'validation_logs': [],
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
