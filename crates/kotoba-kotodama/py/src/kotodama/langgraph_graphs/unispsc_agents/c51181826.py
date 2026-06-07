from langgraph.graph import StateGraph, END

class ProcureState(dict):
    pass

def validate_gmp(state):
    print('Validating GMP certification for Hydroxyprogesterone caproate')
    return {'status': 'validated'}

def check_purity(state):
    print('Verifying chemical purity specifications')
    return {'status': 'verified'}

def finalize_procurement(state):
    print('Finalizing order and logistics plan')
    return {'status': 'complete'}

graph = StateGraph(ProcureState)
graph.add_node('validate_gmp', validate_gmp)
graph.add_node('check_purity', check_purity)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate_gmp')
graph.add_edge('validate_gmp', 'check_purity')
graph.add_edge('check_purity', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
