from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GatewayState(TypedDict):
    config_payload: dict
    validation_logs: Annotated[Sequence[str], operator.add]
    is_compliant: bool

def validate_network_specs(state: GatewayState):
    config = state['config_payload']
    logs = [f'Checking throughput: {config.get("throughput_gbps")} Gbps']
    compliant = config.get("throughput_gbps", 0) >= 10
    return {'validation_logs': logs, 'is_compliant': compliant}

def deploy_gateway(state: GatewayState):
    return {'validation_logs': ['Gateway deployed successfully']}

graph = StateGraph(GatewayState)
graph.add_node('validate', validate_network_specs)
graph.add_node('deploy', deploy_gateway)
graph.add_edge('validate', 'deploy')
graph.add_edge('deploy', END)
graph.set_entry_point('validate')
graph = graph.compile()

# codemod-2605231330-defaults-wrapper
_DEFAULTS_2605231330 = {
    'config_payload': {},
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
