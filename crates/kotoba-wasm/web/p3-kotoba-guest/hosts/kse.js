// kotoba:kais/kse — local journal stub (returns a deterministic topic CID).
export function publish(topic, _payload) {
  return 'bafy-kse-' + topic.replace(/[^a-z0-9]/gi, '').slice(0, 16);
}
export function drain() { return []; }
