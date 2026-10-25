# soko — design

Warehouse / logistics domain library on chobo.ledger (lane `:warehouse`) + shitsuke + mise.

## soko.warehouse
`Warehouse{:id :name :location :zones}`. `Stock{:levels {sku → {wh → qty}}}` (location-aware). `(stock-from triples)`, `(on-hand st sku wh)`, `(total-on-hand st sku)`, `(available? st sku wh needed?)`, `(reserve/restock st sku wh qty)`, `(transfer st sku wh-from wh-to qty)` (atomic, no-op if insufficient), `(warehouses-with-sku st sku)`, `(warehouse-activity opts)` → chobo.ledger activity (lane :warehouse).

## soko.shipment
`Shipment{:id :order-id :warehouse :carrier :tracking :status :lines}`. Status statechart: `:pending → :picked → :packed → :shipped → :delivered` (`:cancelled` from `:pending/:picked`). `(shipment m)`, `(pick/pack/ship/deliver/cancel s)`, `(set-tracking s t)`, `(shipment-activity s opts)`.

## soko.fulfillment
`(can-fulfill? st wh-id lines)`, `(pick-list st lines)` (first-fit allocation, nil if unfulfillable), `(fulfillment-plan st order-id lines)` → `{:pick-list :shipments}` or `{:error :cannot-fulfill}`.

## soko.projection (cross-domain)
Bridges mise.order → soko.fulfillment. `(order-lines ord)` (normalize mise items), `(order->fulfillment-plan ord stock)`, `(can-fulfill-order? ord stock)`, `(fulfillment-activity ord plan opts)` → chobo.ledger activity (lane :warehouse, kind :fulfillment-plan).

## soko.events / views / ssr
re-frame portable 7-fn subset. app-db `{:stock :shipments []}`. events: `:soko/init`, `:stock/restock`, `:stock/reserve`, `:stock/transfer`, `:shipment/add`, `:shipment/transition`. subs: `:soko/stock`, `:soko/on-hand`, `:soko/shipments`. Views: `stock-row`, `shipment-row`, `root`. SSR: `sample-db`, `root-html`.
