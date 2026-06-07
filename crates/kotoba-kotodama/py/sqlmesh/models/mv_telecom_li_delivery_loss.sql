-- Telecom LI delivery loss: IRI and CC delivery counts per ack status.
MODEL (
  name dev.mv_telecom_li_delivery_loss,
  kind FULL,
  dialect postgres,
  description 'Per (delivery_kind=iri|cc, ack_status): delivery count.',
  grain [delivery_kind, ack_status],
  tags [telecom, li, delivery, loss]
);

SELECT 'iri' AS delivery_kind, ack_status, COUNT(*) AS delivery_count
FROM vertex_telecom_li_iri_delivery
GROUP BY ack_status
UNION ALL
SELECT 'cc' AS delivery_kind, ack_status, COUNT(*) AS delivery_count
FROM vertex_telecom_li_cc_delivery
GROUP BY ack_status
