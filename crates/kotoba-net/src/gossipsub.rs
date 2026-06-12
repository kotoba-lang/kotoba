/// GossipSub topic ↔ KSE Journal Topic mapping
pub const MAX_GOSSIPSUB_TOPIC_BYTES: usize = 256;

pub fn gossipsub_topic(kotoba_topic: &str) -> String {
    checked_gossipsub_topic(kotoba_topic).expect("valid gossipsub topic")
}

pub fn checked_gossipsub_topic(kotoba_topic: &str) -> Result<String, String> {
    let mut topic = kotoba_topic.trim_start_matches('/');
    if let Some(rest) = topic.strip_prefix("kotoba/") {
        topic = rest.trim_start_matches('/');
    } else if topic == "kotoba" {
        topic = "";
    }

    if topic.is_empty() {
        return Err("gossipsub topic must not be empty".into());
    }
    if topic.len() > MAX_GOSSIPSUB_TOPIC_BYTES {
        return Err(format!(
            "gossipsub topic exceeds {MAX_GOSSIPSUB_TOPIC_BYTES} byte limit"
        ));
    }
    if topic.bytes().any(|b| b.is_ascii_control()) {
        return Err("gossipsub topic contains control byte".into());
    }
    Ok(format!("kotoba/{topic}"))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn plain_topic_gets_kotoba_prefix() {
        assert_eq!(gossipsub_topic("quad/assert"), "kotoba/quad/assert");
    }

    #[test]
    fn leading_slash_is_stripped() {
        assert_eq!(gossipsub_topic("/quad/assert"), "kotoba/quad/assert");
    }

    #[test]
    fn multiple_leading_slashes_stripped() {
        assert_eq!(
            gossipsub_topic("//pregel/messages"),
            "kotoba/pregel/messages"
        );
    }

    #[test]
    fn empty_topic_is_rejected_by_checked_mapper() {
        assert!(checked_gossipsub_topic("").is_err());
    }

    #[test]
    fn raw_topic_gets_one_kotoba_prefix() {
        let t = gossipsub_topic("pregel/messages");
        assert_eq!(t, "kotoba/pregel/messages");
        assert!(!t.contains("kotoba/kotoba/"), "prefix must not be doubled");
    }

    #[test]
    fn already_prefixed_topic_not_doubled() {
        assert_eq!(
            gossipsub_topic("kotoba/pregel/messages"),
            "kotoba/pregel/messages"
        );
    }

    #[test]
    fn deeply_nested_topic_preserves_all_segments() {
        let t = gossipsub_topic("a/b/c/d/e");
        assert_eq!(t, "kotoba/a/b/c/d/e");
    }

    #[test]
    fn single_segment_topic() {
        assert_eq!(gossipsub_topic("hello"), "kotoba/hello");
    }

    #[test]
    fn topic_with_only_slash_is_rejected() {
        assert!(checked_gossipsub_topic("/").is_err());
    }

    #[test]
    fn topic_with_numbers_and_hyphens() {
        assert_eq!(
            gossipsub_topic("layer-3/block-42"),
            "kotoba/layer-3/block-42"
        );
    }

    #[test]
    fn topic_result_always_starts_with_kotoba_slash() {
        let inputs = ["foo", "/foo", "//foo", "a/b/c", "kotoba/a"];
        for input in inputs {
            let result = gossipsub_topic(input);
            assert!(
                result.starts_with("kotoba/"),
                "result should start with 'kotoba/': got '{result}' for input '{input}'"
            );
        }
    }

    #[test]
    fn trailing_slash_preserved() {
        assert_eq!(gossipsub_topic("topic/"), "kotoba/topic/");
    }

    #[test]
    fn checked_topic_rejects_control_bytes() {
        assert!(checked_gossipsub_topic("quad/\nassert").is_err());
    }

    #[test]
    fn checked_topic_rejects_oversized_topic() {
        assert!(checked_gossipsub_topic(&"a".repeat(MAX_GOSSIPSUB_TOPIC_BYTES + 1)).is_err());
    }
}
