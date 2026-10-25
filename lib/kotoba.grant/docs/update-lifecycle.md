# AiueOS update decision API

`grant.update-lifecycle/decide` extends the existing `grant.ota` and `grant.update`
decisions with security deadlines. It does not fetch, reboot or override the
older admission/health gates. All applicable verdicts must grant. The provider
must bind policy/evidence to the admitted manifest and recheck current owner
policy and an atomic fleet lease immediately before activation.

Default proposal: stable automatic updates in the owner's maintenance window;
security risk high has 72 hours, critical 24 hours after durable first notice.
Manual mode still permits a security deadline only when semi-mandatory policy
was previously authorized. Owner can disable semi-mandatory policy. Defaults
here are decision defaults, not consent or an installed updater.

Application risk is separate: high/critical application risk requires manual
review even after the security deadline. No overdue release bypasses signature,
expiry, compatibility, preserved prior generation, boot recovery or job drain.
Untrusted metadata cannot quarantine a Node. Trusted overdue releases may stop
new fleet jobs while local maintenance stays available. Fleet scheduling must
consume the result; this library does not enforce fleet membership.

`noticed-at` is a durable first notice tied to the manifest digest. Persist it
before notifying. Retry/reboot cannot extend it. Ignore publisher deadlines
shorter than the locally authorized grace. Do not log in-memory monotonic times
as wall-clock timestamps; require trusted time evidence, detect backward jumps,
and hold activation if time/authority evidence is uncertain.

`scripts/update-policy.cljk` provides a JSON stdin/stdout reference port for
kbb. Release fields and evidence use kebab-case names. Node host adapters map
signed `securityRisk`, `applyRisk` etc to these keys. The trial port is a separate
operation, with keyword local-health supplied by the adapter. Production builds
must package the pinned Kotoba runtime/compiled port with its dependencies.

Verification is a pure decision test, not Linux bootloader or Nix qualification.
