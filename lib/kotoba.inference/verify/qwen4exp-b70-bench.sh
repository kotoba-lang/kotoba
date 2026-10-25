#!/usr/bin/env bash
set -euo pipefail

base_model=${QWEN4EXP_BASE_MODEL:-/opt/murakumo-bench/models/Qwen3.8-Flash-Next-UD-IQ1_S/Qwen3.8-Flash-Next-UD-IQ1_S-00001-of-00003.gguf}
draft_model=${QWEN4EXP_MTP_MODEL:-/home/jun/models/Qwen3.8-Flash-Next-MTP/mtp-Qwen3.8-Flash-Next-Q4_K_M.gguf}
engine_dir=${QWEN4EXP_ENGINE_DIR:-/home/jun/murakumo/cafe-llama.cpp/build-sycl/bin}
result_dir=${QWEN4EXP_RESULT_DIR:-/home/jun/murakumo/qwen4exp-mtp-benchmark}
service_unit=${QWEN4EXP_SERVICE_UNIT:-murakumo-b70-vllm.service}
port=${QWEN4EXP_BENCH_PORT:-18080}

mkdir -p "$result_dir"
test -r "$base_model"
test -r "$draft_model"
test -x "$engine_dir/llama-server"

restore_service() {
  sudo systemctl start "$service_unit"
  for _ in $(seq 1 180); do
    curl -fsS http://127.0.0.1:8090/health >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

server_pid=
cleanup() {
  if test -n "$server_pid"; then
    kill "$server_pid" >/dev/null 2>&1 || true
    for _ in $(seq 1 30); do
      kill -0 "$server_pid" >/dev/null 2>&1 || break
      sleep 1
    done
    if kill -0 "$server_pid" >/dev/null 2>&1; then
      kill -9 "$server_pid" >/dev/null 2>&1 || true
    fi
    wait "$server_pid" >/dev/null 2>&1 || true
  fi
  restore_service
}
trap cleanup EXIT INT TERM

sudo systemctl stop "$service_unit"

set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1
set -u

prompt='Write a compact proof that the sum of the first n odd positive integers is n squared.'
request=$(jq -nc --arg prompt "$prompt" '{prompt:$prompt,n_predict:128,temperature:0,seed:42,stream:false,cache_prompt:false,return_tokens:true}')

run_mode() {
  mode=$1
  shift
  log="$result_dir/$mode.server.log"
  : >"$log"
  "$engine_dir/llama-server" -m "$base_model" -ngl auto -fit on \
    --fit-target 4096 --fit-ctx 4096 -fa on \
    -ctk q8_0 -ctv q8_0 -kvu -c 4096 -b 512 -ub 128 --parallel 1 \
    --host 127.0.0.1 --port "$port" "$@" >"$log" 2>&1 &
  server_pid=$!

  ready=0
  for _ in $(seq 1 360); do
    if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      ready=1
      break
    fi
    if ! kill -0 "$server_pid" 2>/dev/null; then
      tail -100 "$log" >&2
      return 1
    fi
    sleep 1
  done
  test "$ready" = 1

  curl -fsS -H 'Content-Type: application/json' -d "$request" \
    "http://127.0.0.1:$port/completion" >"$result_dir/$mode.warm.json"
  for run in 1 2 3; do
    curl -fsS -H 'Content-Type: application/json' -d "$request" \
      "http://127.0.0.1:$port/completion" >"$result_dir/$mode.$run.json"
  done

  kill "$server_pid"
  wait "$server_pid" || true
  server_pid=
}

run_mode off --spec-type none
run_mode on -md "$draft_model" --spec-type draft-mtp --spec-draft-n-max 2

jq -n \
  --slurpfile off1 "$result_dir/off.1.json" \
  --slurpfile off2 "$result_dir/off.2.json" \
  --slurpfile off3 "$result_dir/off.3.json" \
  --slurpfile on1 "$result_dir/on.1.json" \
  --slurpfile on2 "$result_dir/on.2.json" \
  --slurpfile on3 "$result_dir/on.3.json" '
  def sample($mode; $run; $x):
    {mode:$mode,run:$run,tokens:$x.tokens,tokens_predicted:$x.tokens_predicted,
     content:$x.content,predicted_per_second:$x.timings.predicted_per_second,
     prompt_per_second:$x.timings.prompt_per_second,
     end_to_end_tok_s:($x.tokens_predicted*1000/($x.timings.prompt_ms+$x.timings.predicted_ms))};
  [sample("off";1;$off1[0]),sample("off";2;$off2[0]),sample("off";3;$off3[0]),
   sample("on";1;$on1[0]),sample("on";2;$on2[0]),sample("on";3;$on3[0])] as $samples |
  ($samples|map(select(.mode=="off")|.predicted_per_second)|sort|.[1]) as $off_median |
  ($samples|map(select(.mode=="on")|.predicted_per_second)|sort|.[1]) as $on_median |
  ($samples|map(select(.mode=="off")|.end_to_end_tok_s)|sort|.[1]) as $off_e2e_median |
  ($samples|map(select(.mode=="on")|.end_to_end_tok_s)|sort|.[1]) as $on_e2e_median |
  ($samples|map(select(.mode=="off")|.tokens)) as $off_tokens |
  ($samples|map(select(.mode=="on")|.tokens)) as $on_tokens |
  {schema:"kotodama.qwen4exp-mtp-benchmark.v1",samples:$samples,
   off_deterministic:($off_tokens|unique|length==1),
   on_deterministic:($on_tokens|unique|length==1),
   token_parity:($on_tokens|all(. == $off_tokens[0])),
   first_divergence_by_on_run:($on_tokens|map(. as $tokens |
     ([range(0;([$off_tokens[0]|length,$tokens|length]|min)) |
       select($off_tokens[0][.] != $tokens[.])][0] // null))),
   content_parity:($samples|map(.content)|unique|length==1),
   off_median_tok_s:$off_median,on_median_tok_s:$on_median,
   generation_speedup:($on_median/$off_median),
   off_median_end_to_end_tok_s:$off_e2e_median,
   on_median_end_to_end_tok_s:$on_e2e_median,
   end_to_end_speedup:($on_e2e_median/$off_e2e_median)}' >"$result_dir/summary.json"

cat "$result_dir/summary.json"
jq -e '.off_deterministic and .on_deterministic and .token_parity' \
  "$result_dir/summary.json" >/dev/null
