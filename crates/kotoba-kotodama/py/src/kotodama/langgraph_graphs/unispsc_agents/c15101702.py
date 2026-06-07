from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MineralProcessState(TypedDict):
    ore_batch_id: str
    assay_results: dict
    compliance_score: float
    processing_steps: Annotated[List[str], add_messages]

def validate_ore_grade(state: MineralProcessState):
    grade = state['assay_results'].get('ore_grade_percentage', 0)
    return {'compliance_score': 1.0 if grade > 45.0 else 0.0}

def execute_refinement_workflow(state: MineralProcessState):
    return {'processing_steps': ['crushing', 'flotation', 'leaching']}

def build_mineral_graph():
    workflow = StateGraph(MineralProcessState)
    workflow.add_node('validate', validate_ore_grade)
    workflow.add_node('refine', execute_refinement_workflow)
    workflow.set_entry_point('validate')
    workflow.add_edge('validate', 'refine')
    workflow.add_edge('refine', END)
    return workflow.compile()

graph = build_mineral_graph()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'ore_batch_id': "",
    'assay_results': {},
    'compliance_score': 0.0,
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
