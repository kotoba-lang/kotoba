//! Lightweight tokenizer loader for host-side orchestration.
//!
//! This prefers HuggingFace `tokenizer.json` / `tokenizer_config.json` when
//! present and falls back to deterministic byte-level tokenization.

use serde_json::Value;
use std::collections::HashMap;
use std::path::Path;

#[derive(Debug, Clone, Default)]
pub struct SimpleTokenizer {
    vocab: HashMap<String, u32>,
    inverse_vocab: HashMap<u32, String>,
    unk_token_id: Option<u32>,
}

impl SimpleTokenizer {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn load_from_dir(model_dir: &Path) -> Self {
        let mut tokenizer = Self::new();
        tokenizer.load_tokenizer_json(model_dir);
        tokenizer.load_tokenizer_config(model_dir);
        tokenizer
    }

    pub fn encode(&self, text: &str) -> Vec<u32> {
        if self.vocab.is_empty() {
            return self.encode_bytes(text);
        }

        let mut out = Vec::new();
        let mut chars = text.chars().peekable();
        let mut at_word_start = true;

        while let Some(ch) = chars.peek().copied() {
            if ch.is_whitespace() {
                let mut space = String::new();
                while let Some(next) = chars.peek().copied() {
                    if next.is_whitespace() {
                        space.push(next);
                        chars.next();
                    } else {
                        break;
                    }
                }
                out.extend(self.encode_segment(&space, false));
                at_word_start = true;
                continue;
            }

            let mut word = String::new();
            while let Some(next) = chars.peek().copied() {
                if !next.is_whitespace() {
                    word.push(next);
                    chars.next();
                } else {
                    break;
                }
            }
            out.extend(self.encode_segment(&word, at_word_start));
            at_word_start = false;
        }

        if out.is_empty() {
            out.push(self.unk_token_id.unwrap_or(3));
        }
        out
    }

    pub fn decode(&self, token_ids: &[u32]) -> String {
        if self.inverse_vocab.is_empty() {
            let mut bytes = Vec::with_capacity(token_ids.len());
            for &token in token_ids {
                bytes.push(self.decode_token_to_byte(token));
            }
            return String::from_utf8_lossy(&bytes).to_string();
        }

        let mut out = String::new();
        for &token in token_ids {
            if let Some(piece) = self.inverse_vocab.get(&token) {
                if piece == "<unk>" {
                    continue;
                }
                if let Some(stripped) = piece.strip_prefix('Ġ') {
                    out.push(' ');
                    out.push_str(stripped);
                } else if let Some(stripped) = piece.strip_prefix('▁') {
                    out.push(' ');
                    out.push_str(stripped);
                } else {
                    out.push_str(piece);
                }
            } else {
                out.push(self.decode_token_to_byte(token) as char);
            }
        }
        out
    }

    pub fn decode_token_to_byte(&self, token_id: u32) -> u8 {
        token_id.saturating_sub(3).min(255) as u8
    }

    fn encode_segment(&self, segment: &str, at_word_start: bool) -> Vec<u32> {
        if segment.is_empty() {
            return Vec::new();
        }
        if let Some(id) = self.match_piece(segment, at_word_start) {
            return vec![id];
        }

        let mut out = Vec::new();
        let mut buffer = String::new();
        for ch in segment.chars() {
            buffer.push(ch);
            if let Some(id) = self.match_piece(&buffer, at_word_start && out.is_empty()) {
                out.push(id);
                buffer.clear();
            } else {
                let fallback = self.encode_bytes(&buffer);
                out.extend(fallback);
                buffer.clear();
            }
        }
        if !buffer.is_empty() {
            out.extend(self.encode_bytes(&buffer));
        }
        out
    }

    fn match_piece(&self, segment: &str, at_word_start: bool) -> Option<u32> {
        self.vocab
            .get(segment)
            .copied()
            .or_else(|| {
                if at_word_start {
                    self.vocab
                        .get(&format!("Ġ{segment}"))
                        .copied()
                        .or_else(|| self.vocab.get(&format!("▁{segment}")).copied())
                } else {
                    None
                }
            })
            .or_else(|| {
                if segment == " " {
                    self.vocab.get("Ġ").copied().or_else(|| self.vocab.get("▁").copied())
                } else {
                    None
                }
            })
    }

    fn encode_bytes(&self, text: &str) -> Vec<u32> {
        let mut out = Vec::with_capacity(text.len().max(1));
        for &byte in text.as_bytes() {
            out.push(byte as u32 + 3);
        }
        if out.is_empty() {
            out.push(3);
        }
        out
    }

    fn load_tokenizer_json(&mut self, model_dir: &Path) {
        let path = model_dir.join("tokenizer.json");
        let Ok(body) = std::fs::read_to_string(&path) else {
            return;
        };
        let Ok(value) = serde_json::from_str::<Value>(&body) else {
            return;
        };

        if let Some(vocab) = value
            .get("model")
            .and_then(|m| m.get("vocab"))
            .and_then(|v| v.as_object())
        {
            for (token, id) in vocab {
                if let Some(id) = id.as_u64() {
                    self.vocab.insert(token.clone(), id as u32);
                    self.inverse_vocab.insert(id as u32, token.clone());
                }
            }
        }

        if let Some(added_tokens) = value.get("added_tokens").and_then(|v| v.as_array()) {
            for token in added_tokens {
                let Some(content) = token.get("content").and_then(|v| v.as_str()) else {
                    continue;
                };
                let Some(id) = token.get("id").and_then(|v| v.as_u64()) else {
                    continue;
                };
                self.vocab.insert(content.to_string(), id as u32);
                self.inverse_vocab.insert(id as u32, content.to_string());
            }
        }
    }

    fn load_tokenizer_config(&mut self, model_dir: &Path) {
        let path = model_dir.join("tokenizer_config.json");
        let Ok(body) = std::fs::read_to_string(&path) else {
            return;
        };
        let Ok(value) = serde_json::from_str::<Value>(&body) else {
            return;
        };
        if let Some(unk) = value.get("unk_token").and_then(|v| v.as_str()) {
            self.unk_token_id = self.vocab.get(unk).copied();
        }
    }
}
