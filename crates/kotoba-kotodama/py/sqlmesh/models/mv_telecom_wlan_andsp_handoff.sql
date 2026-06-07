-- Telecom WLAN ANDSP handoff: ANDSP bridge counts per ATSSS mode/transition/status.
MODEL (
  name dev.mv_telecom_wlan_andsp_handoff,
  kind FULL,
  dialect postgres,
  description 'Per (atsss_mode, transition_kind, status): WLAN ANDSP bridge count.',
  grain [atsss_mode, transition_kind, status],
  tags [telecom, wlan, andsp, handoff]
);

SELECT
  atsss_mode,
  transition_kind,
  status,
  COUNT(*) AS bridge_count
FROM vertex_telecom_wlan_andsp_bridge
GROUP BY atsss_mode, transition_kind, status
