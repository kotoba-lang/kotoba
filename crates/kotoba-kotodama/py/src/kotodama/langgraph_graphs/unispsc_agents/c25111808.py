from langgraph.graph import StateGraph, END
from typing import TypedDict

class YachtProcurementState(TypedDict):
    vessel_id: str
    compliance_passed: bool
    inspection_report: str

def validate_yacht_specs(state: YachtProcurementState):
    print(f"Validating yacht specifications for vessel {state['vessel_id']}")
    return {"compliance_passed": True}

def conduct_maritime_inspection(state: YachtProcurementState):
    print("Executing marine survey and inspection.")
    return {"inspection_report": "Survey Passed: Hull integrity confirmed."}

defgraph = StateGraph(YachtProcurementState)
defgraph.add_node("validate", validate_yacht_specs)
defgraph.add_node("inspect", conduct_maritime_inspection)
defgraph.set_entry_point("validate")
defgraph.add_edge("validate", "inspect")
defgraph.add_edge("inspect", END)
graph = defgraph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'vessel_id': "",
    'compliance_passed': False,
    'inspection_report': ""
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
