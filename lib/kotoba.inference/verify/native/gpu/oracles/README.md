# tokenizer oracles not shipped by llama.cpp

`ggml-vocab-gpt-neox.gguf.{inp,out}` — pre type `default` (the GGUF carries no `tokenizer.ggml.pre`).
llama.cpp ships `models/ggml-vocab-gpt-neox.gguf` but no `.inp/.out` for it; these 62 texts (llama.cpp's
`ggml-vocab-llama-bpe.gguf.inp` 46 + `tokenizer_corpus.txt` 13 + 3 punctuation / digit-grouping stress lines) were
tokenized by `llama-tokenize --ids --no-bos --no-parse-special -f` of llama.cpp 911f6cdc (2026-09-20).
Run: `kbb --backend sci ../tokenizer_oracle.cljk <llama.cpp>/models/ggml-vocab-gpt-neox.gguf oracles/ggml-vocab-gpt-neox.gguf`
