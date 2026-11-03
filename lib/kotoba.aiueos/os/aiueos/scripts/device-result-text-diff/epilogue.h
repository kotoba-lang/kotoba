  for (uint32_t i = 0; i < body.length; i++) body_out[i] = body.bytes[i];
  body_length = body.ok ? body.length : 0;
cleanup:
  return body_length;
}
