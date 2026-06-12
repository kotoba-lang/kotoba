from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ForensicState(TypedDict):
    incident_id: str
    evidence_hash: str
    extracted_data_path: str
    processing_steps: Annotated[List[str], add_messages]

def initialize_forensic(state: ForensicState):
    return {'processing_steps': [f'Initializing forensic suite for incident {state["incident_id"]}']}

def perform_data_extraction(state: ForensicState):
    return {'processing_steps': [f'Extracting data from {state["extracted_data_path"]}', 'Verifying integrity with hash ' + state['evidence_hash']]}

def secure_vault_audit(state: ForensicState):
    return {'processing_steps': ['Auditing secure vault logs', 'Finalizing evidentiary report']}

graph = StateGraph(ForensicState)
graph.add_node('init', initialize_forensic)
graph.add_node('extract', perform_data_extraction)
graph.add_node('audit', secure_vault_audit)
graph.set_entry_point('init')
graph.add_edge('init', 'extract')
graph.add_edge('extract', 'audit')
graph.add_edge('audit', END)
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'incident_id': "",
    'evidence_hash': "",
    'extracted_data_path': "",
    'processing_steps': []
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
