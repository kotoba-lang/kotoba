"""Golden vectors for the hermes turn loop, from the UPSTREAM source.

IterationBudget is imported from the real checkout -- not reimplemented -- so
the budget half of the contract is the upstream's own code. The admission half
is transcribed from agent/conversation_loop.py:2074..2115, and the transcription
is what the parity test is for.
"""
import sys, json
sys.path.insert(0, "/Users/junkawasaki/.hermes/hermes-agent")
from agent.iteration_budget import IterationBudget   # the real one

# conversation_loop.py:2074
#   while (api_call_count < max_iterations and budget.remaining > 0) or grace:
#       if interrupt_requested:            -> "interrupted_by_user"
#       if review_input_budget_exhausted:  -> "review_input_budget_exhausted"
#       api_call_count += 1
#       if grace: grace = False
#       elif not budget.consume():         -> "budget_exhausted"
#   (loop condition false)                 -> "max_iterations_reached"
def run(max_iterations, budget_max, events):
    b = IterationBudget(budget_max)
    n = 0
    grace = False
    trace = []
    for ev in events:
        if ev == "grace-grant":
            grace = True
            trace.append(("grace-grant", n, b.used, grace, "running"))
            continue
        if ev == "refund":
            b.refund()
            trace.append(("refund", n, b.used, grace, "running"))
            continue
        if ev == "interrupt":
            trace.append(("interrupt", n, b.used, grace, "interrupted_by_user"))
            return trace, "interrupted_by_user", n, b.used
        if ev == "review-budget-exhausted":
            trace.append((ev, n, b.used, grace, "review_input_budget_exhausted"))
            return trace, "review_input_budget_exhausted", n, b.used
        # ev == "tick": one attempted iteration
        if not ((n < max_iterations and b.remaining > 0) or grace):
            trace.append(("tick", n, b.used, grace, "max_iterations_reached"))
            return trace, "max_iterations_reached", n, b.used
        n += 1
        if grace:
            grace = False
        elif not b.consume():
            trace.append(("tick", n, b.used, grace, "budget_exhausted"))
            return trace, "budget_exhausted", n, b.used
        trace.append(("tick", n, b.used, grace, "running"))
    return trace, "running", n, b.used

CASES = [
    ("plain-3",            5, 5, ["tick","tick","tick"]),
    ("hit-max-iterations", 2, 9, ["tick","tick","tick"]),
    ("hit-budget",         9, 2, ["tick","tick","tick"]),
    ("interrupt-mid",      5, 5, ["tick","interrupt","tick"]),
    ("review-budget",      5, 5, ["tick","review-budget-exhausted"]),
    ("refund-extends",     9, 2, ["tick","tick","refund","tick"]),
    ("grace-past-max",     1, 9, ["tick","grace-grant","tick","tick"]),
    ("grace-past-budget",  9, 1, ["tick","grace-grant","tick","tick"]),
    ("zero-budget",        5, 0, ["tick"]),
    ("zero-iterations",    0, 5, ["tick"]),
]
out=[]
for name, mx, bm, evs in CASES:
    trace, reason, n, used = run(mx, bm, evs)
    out.append({"name":name,"max_iterations":mx,"budget_max":bm,"events":evs,
                "exit_reason":reason,"api_call_count":n,"budget_used":used})
print(json.dumps(out, indent=1))
