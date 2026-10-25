(ns madoguchi.projection
  "Cross-domain projection: mise.order → madoguchi ticket.

  Bridges retail EC (mise) and support (madoguchi): a customer inquiry about an
  order (sizing, shipping, defect) creates a support ticket linked to the order.
  v1 is pure — the host app persists the ticket via its store."
  (:require [madoguchi.ticket :as ticket]
            [chobo.ledger :as ledger]))

(defn order->ticket
  "Build a new support ticket from a mise order + inquiry subject. The ticket
  starts at :new with :normal priority, referencing the order id in props."
  ([ord subject]
   (order->ticket ord subject {}))
  ([ord subject opts]
   (ticket/ticket
    (merge {:id (str "tkt_" (hash (:id ord)))
            :customer (or (:account-id ord) (:account-id opts) (:customer opts) "unknown")
            :subject subject
            :priority (:priority opts :normal)
            :props {:order-id (:id ord)}}
           (select-keys opts [:assignee :sla-due :created-at])))))

(defn inquiry-activity
  "Project the order→ticket event onto chobo.ledger as a :support activity
  (kind :order-inquiry). Caller appends."
  [ord ticket' opts]
  (ledger/activity
   (merge {:lane :support :kind :order-inquiry
           :title (:subject ticket')
           :state (:status ticket' :new)
           :props {:order-id (:id ord) :ticket-id (:id ticket')}}
          opts)))
