# cloud-itonami × product-party

## Runtime flow

```text
operator / workspace effect
        |
        v
cloud-itonami.product-party  (tenant MemStore + governor hints)
        |
        v
kotoba.product-party         (pure bind / query / bridge)
        |
        +---> itonami.store supplier shape   (procurement genealogy)
        +---> goyoukiki unspsc-tags          (tender match)
        +---> kotoba.unspsc segment          (open-business blueprint)
        +---> kotoba.industry ISIC           (industry blueprint)
```

Identity SSoT stays outside:

- GTIN product masters → etzhayyim GTIN / uchiwake
- `org.corp.*` companies → etzhayyim kabuto
- 8-digit UNSPSC commodity table → etzhayyim `20-actors/unspsc`

## Effects (cloud-itonami)

| Kind | Meaning |
|---|---|
| `:product-party/bind` | attach party role to product (high-stakes roles → human gate) |
| `:product-party/revoke` | revoke an edge with reason |
| `:product-party/upsert-product` | tenant projection of a trade item |
| `:product-party/upsert-party` | tenant projection of a company/supplier/merchant |

## Why not put masters here?

ADR-2607031800 already refused a code-keyed GTIN blueprint fleet (GTIN is an
identifier, not a classification). ADR-2607031700 split UNSPSC segment
blueprints from the commodity actor for the same reason. `product-party`
follows that pattern: **join contract only**, no competing masters.
