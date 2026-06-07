-- Datacenter capacity reserved: aggregated approved reservations per facility.
MODEL (
  name dev.mv_datacenter_capacity_reserved,
  kind FULL,
  dialect postgres,
  description 'Per facility: total reserved rack units, power (kW), and cooling (kW) from approved capacity reservations.',
  grain [facility_id],
  tags [datacenter, capacity, reservation, power, cooling]
);

SELECT
  facility_id,
  COALESCE(SUM(rack_units), 0) AS reserved_rack_units,
  COALESCE(SUM(power_kw), 0) AS reserved_power_kw,
  COALESCE(SUM(cooling_kw), 0) AS reserved_cooling_kw
FROM vertex_datacenter_capacity_reservation
WHERE status = 'approved'
GROUP BY facility_id
