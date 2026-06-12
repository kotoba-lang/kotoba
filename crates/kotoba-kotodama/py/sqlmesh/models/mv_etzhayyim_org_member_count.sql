-- Etzhayyim org member count: role and invite status breakdown per org.
MODEL (
  name dev.mv_etzhayyim_org_member_count,
  kind FULL,
  dialect postgres,
  description 'Per org_did: member counts by role (owner/admin/member/viewer/agent) and invite status (accepted/pending).',
  grain [org_did],
  tags [etzhayyim, org, member, role]
);

SELECT
  dst_vid AS org_did,
  COUNT(*) AS total_members,
  COUNT(*) FILTER (WHERE role = 'owner') AS owner_count,
  COUNT(*) FILTER (WHERE role = 'admin') AS admin_count,
  COUNT(*) FILTER (WHERE role = 'member') AS member_count,
  COUNT(*) FILTER (WHERE role = 'viewer') AS viewer_count,
  COUNT(*) FILTER (WHERE role = 'agent-runtime') AS agent_count,
  COUNT(*) FILTER (WHERE invite_status = 'accepted') AS accepted_count,
  COUNT(*) FILTER (WHERE invite_status = 'pending') AS pending_count
FROM edge_etzhayyim_member_of
GROUP BY dst_vid
