-- Open smartphone OS CVE exposure: active OS builds with patch level and verified boot status.
MODEL (
  name dev.mv_open_smartphone_os_cve_exposure,
  kind FULL,
  dialect postgres,
  description 'Active OS builds: name, version, latest patch level, open blobs pct, verified boot.',
  grain [os_build_id],
  tags [open_smartphone, os, cve, exposure]
);

SELECT
  b.vertex_id AS os_build_id,
  b.os_name,
  b.version,
  b.patch_level AS latest_patch_level,
  b.open_blobs_pct,
  b.verified_boot
FROM vertex_open_smartphone_os_build b
WHERE b.status = 'active'
