# soko

`soko`（倉庫）— kotoba-lang shared **warehouse / logistics** domain library:
multi-location stock, shipments, fulfillment planning. Portable .cljc on
[`chobo.ledger`](../chobo) (lane `:warehouse`) + [`shitsuke`](../shitsuke) +
[`mise`](../mise) (inventory interop). Zero host effects.

| layer | role |
|---|---|
| `soko.warehouse` | Warehouse + location-aware Stock {sku×wh→qty} + reserve/restock/transfer + ledger projection |
| `soko.shipment` | Shipment + status statechart (pending→picked→packed→shipped→delivered) + tracking |
| `soko.fulfillment` | fulfillment plan (pick-list + per-warehouse shipments; first-fit allocation) |
| `soko.events` | re-frame events/subs (portable 7-fn subset) |
| `soko.views` | pure-hiccup: stock-row, shipment-row |
| `soko.ssr` | SSR parity |

```bash
kbb -M:test       # published deps
kbb -M:local:test # local ../shitsuke ../chobo ../mise
```

See `docs/design.md` and `docs/adr/0001-soko-warehouse-logistics.md`.
