import time
from typing import cast

from kotodama.organism.inbox import InboxBuffer, _MAX_OBSERVATIONS
from kotodama.organism.memory import KotobaKqeMemory
from kotodama.organism.observation import TextObservation


def test_warm_flush_roundtrip():
    memory = KotobaKqeMemory()
    now = int(time.time() * 1000)

    obs1 = TextObservation(actorDid="did:example:1", createdAt=now, tier="A", text="hello")
    obs2 = TextObservation(actorDid="did:example:1", createdAt=now + 100, tier="B", text="world")
    obs3 = TextObservation(actorDid="did:example:2", createdAt=now + 200, tier="A", text="other")

    # Flush to warm
    cids = memory.warm_flush([obs1, obs2, obs3])
    assert len(cids) == 3
    assert all(cid.startswith("bafyreq") for cid in cids)

    # Lookup by actor
    actor1_obs = memory.warm_lookup("did:example:1", kind=None, n=10)
    assert len(actor1_obs) == 2
    # Should be returned most recent first
    assert actor1_obs[0].text == "world"
    assert actor1_obs[1].text == "hello"

    # Lookup by kind
    text_obs = memory.warm_lookup("did:example:1", kind="text", n=1)
    assert len(text_obs) == 1
    assert text_obs[0].text == "world"


def test_inbox_flush_hook():
    inbox = InboxBuffer()
    memory = KotobaKqeMemory()
    now = int(time.time() * 1000)

    # Fill inbox to 75% exactly
    threshold = int(_MAX_OBSERVATIONS * 0.75)
    for i in range(threshold):
        inbox.push(TextObservation(actorDid="did:example:1", createdAt=now+i, tier="A", text=f"msg {i}"))

    # Should not flush yet
    cids = inbox.flush_to_warm(memory)
    assert len(cids) == 0
    assert len(inbox.observations) == threshold

    # Push one more to exceed 75%
    inbox.push(TextObservation(actorDid="did:example:1", createdAt=now+threshold, tier="A", text="msg trigger"))

    # Flush
    cids = inbox.flush_to_warm(memory)
    keep_count = int(_MAX_OBSERVATIONS * 0.25)
    expected_flush_count = (threshold + 1) - keep_count

    assert len(cids) == expected_flush_count
    assert len(inbox.observations) == keep_count

    # Verify the oldest were flushed and the newest were kept
    assert inbox.observations[0].text == f"msg {expected_flush_count}"
    assert inbox.observations[-1].text == "msg trigger"


def test_provenance_hash_chain():
    memory = KotobaKqeMemory()
    now = int(time.time() * 1000)

    assert memory.current_provenance_hash == "genesis"

    obs1 = TextObservation(actorDid="did:example:1", createdAt=now, tier="A", text="first")
    memory.warm_flush([obs1])
    hash1 = memory.current_provenance_hash
    assert hash1 != "genesis"

    obs2 = TextObservation(actorDid="did:example:1", createdAt=now+1, tier="A", text="second")
    memory.warm_flush([obs2])
    hash2 = memory.current_provenance_hash
    assert hash2 != hash1


def test_tier_c_internal_only():
    inbox = InboxBuffer()
    memory = KotobaKqeMemory()
    now = int(time.time() * 1000)

    # Push a tier C observation
    obs = TextObservation(actorDid="did:example:1", createdAt=now, tier="C", text="internal thought")
    inbox.push(obs)

    assert len(inbox.observations) == 1
    # internal_only flag should be bound by push()
    assert inbox.observations[0].internal_only is True

    # Force a flush by filling up the buffer
    threshold = int(_MAX_OBSERVATIONS * 0.75)
    for i in range(threshold):
        inbox.push(TextObservation(actorDid="did:example:1", createdAt=now+i+1, tier="A", text=f"msg {i}"))

    cids = inbox.flush_to_warm(memory)
    assert len(cids) > 0

    # Look it up from warm memory (need to look up enough to find the oldest one)
    warm_obs = memory.warm_lookup("did:example:1", kind=None, n=100)
    # The oldest (flushed) ones are at the end of the lookup since lookup returns reverse chronological
    internal_obs = [o for o in warm_obs if o.text == "internal thought"]
    assert len(internal_obs) == 1
    assert internal_obs[0].tier == "C"
    assert internal_obs[0].internal_only is True
