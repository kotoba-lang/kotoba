from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END

class MineralProcessState(TypedDict):
    material_id: str
    purity: float
    process_steps: List[str]
    validation_errors: List[str]

def validate_catalyst(state: MineralProcessState):
    errors = []
    if state['purity'] < 0.98:
        errors.append('Purity below 98% threshold')
    return {'validation_errors': errors}

def process_refining(state: MineralProcessState):
    if not state['validation_errors']:
        return {'process_steps': ['calcination', 'catalytic_activation', 'quality_assay']}
    return {'process_steps': ['quarantine']}

def compile_graph():
    workflow = StateGraph(MineralProcessState)
    workflow.add_node('validate', validate_catalyst)
    workflow.add_node('refine', process_refining)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', 'refine')
    workflow.add_edge('refine', END)
    return workflow.compile()

graph = compile_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'material_id': "",
    'purity': 0.0,
    'process_steps': [],
    'validation_errors': []
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
