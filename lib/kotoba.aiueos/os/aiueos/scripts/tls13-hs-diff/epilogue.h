/* One run: reset the state, feed the stream in chunks, and report the trace and the final state. */
int PFX(run)(const uint8_t *stream, uint32_t len, uint32_t chunk, uint32_t script_seed, uint64_t out[8]) {
  uint32_t at = 0; int ok = 1;
  transcript_len = rx_len = hs_partial_len = app_len = 0;
  saw_record = have_sh = have_hs_keys = have_server_finished = handshake_ready = failed = certverify_parsed = have_leaf_pub = 0;
  first_record_type = last_record_type = last_inner_type = 0; last_alert_level = last_alert_desc = 0; nst_count = 0;
  s_hs_seq = s_ap_seq = 0; trace = 0; calls = 0; script = script_seed;
  while (at < len && ok) { uint32_t n = len - at < chunk ? len - at : chunk; ok = aiueos_tls13_feed(stream + at, n); at += n; }
  out[0] = trace; out[1] = calls | ((uint64_t)ok << 32);
  out[2] = (uint64_t)failed | (uint64_t)handshake_ready << 1 | (uint64_t)have_sh << 2 | (uint64_t)have_hs_keys << 3 |
           (uint64_t)have_server_finished << 4 | (uint64_t)certverify_parsed << 5 | (uint64_t)saw_record << 6;
  out[3] = first_record_type | (uint64_t)last_record_type << 8 | (uint64_t)last_inner_type << 16 |
           (uint64_t)last_alert_level << 24 | (uint64_t)last_alert_desc << 32;
  out[4] = app_len | (uint64_t)sum(app_buf, app_len) << 32;
  out[5] = transcript_len | (uint64_t)sum(transcript, transcript_len) << 32;
  out[6] = hs_partial_len | (uint64_t)rx_len << 32;
  out[7] = nst_count | (uint64_t)s_hs_seq << 32 | (uint64_t)s_ap_seq << 48;
  return ok;
}
