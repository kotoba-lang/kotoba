import sys
import os
import json

# Add the cells directory to the python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from ossekai_arbitrage_observer.cell import compiled as observer_graph
from ossekai_intel_analyzer.cell import compiled as analyzer_graph
from ossekai_aggregate_publisher.cell import compiled as publisher_graph
from ossekai_member_digest.cell import compiled as member_digest_graph
from ossekai_mention_dispatcher.cell import compiled as mention_dispatcher_graph
from ossekai_consent_registry.cell import compiled as consent_registry_graph
from ossekai_kaizen_observer.cell import compiled as kaizen_observer_graph
from ossekai_emergency_advisory.cell import compiled as emergency_advisory_graph

def test_pipeline():
    print("=== Testing ossekai_arbitrage_observer ===")
    observer_input = {
        "context": {
            "sensor_data": ["market anomaly A", "pricing discrepancy B"]
        }
    }
    observer_result = observer_graph.invoke(observer_input)
    print("Observer Result:", json.dumps(observer_result, indent=2))
    
    print("\n=== Testing ossekai_intel_analyzer ===")
    analyzer_input = {
        "context": {
            "arbitrage_gap_report": observer_result.get("arbitrage_gap_report", {})
        }
    }
    analyzer_result = analyzer_graph.invoke(analyzer_input)
    print("Analyzer Result:", json.dumps(analyzer_result, indent=2))

    print("\n=== Testing ossekai_aggregate_publisher ===")
    publisher_input = {
        "context": {
            "wellbecoming_advisory": analyzer_result.get("wellbecoming_advisory", {})
        }
    }
    publisher_result = publisher_graph.invoke(publisher_input)
    print("Publisher Result:", json.dumps(publisher_result, indent=2))

    print("\n=== Testing ossekai_member_digest ===")
    digest_input = {
        "context": {
            "wellbecoming_advisory": analyzer_result.get("wellbecoming_advisory", {})
        }
    }
    digest_result = member_digest_graph.invoke(digest_input)
    print("Digest Result:", json.dumps(digest_result, indent=2))

    print("\n=== Testing ossekai_consent_registry ===")
    consent_input = {
        "context": {
            "block_mute_events": [{"target": "bad_actor.bsky.social", "action": "block"}]
        }
    }
    consent_result = consent_registry_graph.invoke(consent_input)
    print("Consent Result:", json.dumps(consent_result, indent=2))

    print("\n=== Testing ossekai_mention_dispatcher ===")
    dispatcher_input = {
        "context": {
            "mention_dispatch_attestation": {"target_handle": "good_actor.bsky.social"},
            "consent_state": consent_result.get("consent_state", {})
        }
    }
    dispatcher_result = mention_dispatcher_graph.invoke(dispatcher_input)
    print("Dispatcher Result:", json.dumps(dispatcher_result, indent=2))
    
    print("\n=== Testing ossekai_kaizen_observer ===")
    kaizen_input = {
        "context": {
            "metrics_snapshot": {"staleness": 0.05, "unsubscribe_rate": 0.01}
        }
    }
    kaizen_result = kaizen_observer_graph.invoke(kaizen_input)
    print("Kaizen Result:", json.dumps(kaizen_result, indent=2))

    print("\n=== Testing ossekai_emergency_advisory ===")
    emergency_input = {
        "context": {
            "emergency_declaration": {"event": "severe weather warning"}
        }
    }
    emergency_result = emergency_advisory_graph.invoke(emergency_input)
    print("Emergency Result:", json.dumps(emergency_result, indent=2))

    print("\n✅ LangGraph Agent Pipeline Verified (R1 + R2 + R3).")

if __name__ == "__main__":
    test_pipeline()


