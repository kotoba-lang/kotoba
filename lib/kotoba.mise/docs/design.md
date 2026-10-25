# mise — design

Layer-by-layer API reference for `mise` (the kotoba-lang shared EC system).
For the *why* see `docs/adr/0001-mise-ec-system.md`.

## mise.catalog

```
Product  {:id :brand :name :category :description :images [..] :variants [SKU..]}
SKU      {:id :product-id :name :options {} :price Price}
Catalog  {:products [] :categories {}}
```
- `(catalog products categories?)` → Catalog
- `(product-by-id src id)`, `(products-by-category src cat)`, `(search src q)`
- `(sku-by-id src product-id sku-id)` / `(sku-by-id product sku-id)`
- `(default-sku product)` — first variant or the product itself if no variants

## mise.pricing

`Price{:amount :currency}`. Pure arithmetic; no host effects.
- `(price amount currency?)`, `(zero-price currency?)`, `(add a b)`, `(multiply p n)`, `(line-total unit qty)`
- `IDiscount` port (`apply-discount [ctx subtotal] → Price`); `(no-discount)`.
- `ITax` port (`compute-tax [ctx subtotal] → Price`); `(flat-tax rate)`.
- `IShipping` port (`compute-shipping [ctx subtotal] → Price`); `(free-shipping)`.
- `(subtotal lines)`, `(totals lines opts)` → `{:subtotal :discount :tax :shipping :total}`.
- `(format-price p opts?)` → `"¥12,800"` (portable, no java.text).

## mise.cart

`Cart{:lines [{:sku :qty :unit-price :name ...}]}`. Pure; invariants: qty pos-int, deduped by :sku.
- `(cart)`, `(add-line cart line)`, `(update-qty cart sku qty)` (≤0 removes), `(remove-line cart sku)`, `(clear cart)`
- `(line-count cart)`, `(item-count cart)`, `(empty? cart)`, `(totals cart opts?)`.

## mise.inventory

`Stock{:levels {sku → qty}}`. Pure.
- `(stock m)`, `(on-hand stock sku)`, `(available? stock sku needed?)`, `(reserve stock sku qty)`, `(restock ...)`, `(set-level ...)`, `(reserve-many stock [[sku qty]...])`.

## mise.checkout

`Checkout{:stage :contact :shipping :payment :cart :order-id}`. Stages: `:contact → :shipping → :payment → :review → :confirmed`.
- `required-fields` per stage; `(validate-stage co stage)` → missing seq or nil.
- `(checkout cart fields?)`, `(set-field co stage key val)`, `(set-fields co stage m)`, `(next-stage co)` → `{:ok co}` | `{:errors [..] :checkout co}`, `(prev-stage co)`.
- `IPaymentPort` (`authorize [ctx amount] → {:ref :status :amount}` / `capture [ctx ref]`); `(mock-payment-port)`.
- `(place-order co payment-port opts)` → `{:ok co :order ord}` | `{:error .. :checkout co}`. Requires stage `:review`.

## mise.order

`Order{:id :items :shipping :contact :payment-ref :status :totals :created-at}`. Statechart:
`:pending → :paid → :fulfilled`; `:cancelled` from `:pending`/`:paid`.
- `(order m)`, `(can-transition? from to)`, `(transition ord to)`, `(mark-paid ord)`, `(mark-fulfilled ord)`, `(cancel ord)`.
- `IOrderStore` port (`put-order! [ord]` / `get-order [id]` / `list-orders`); `(mock-order-store)`.

## mise.events (re-frame, portable subset)

Registered via `(register!)` against `shitsuke.re-frame.core` (mini runtime on JVM, real re-frame on cljs). app-db:
```
{:catalog <Catalog> :cart <Cart> :checkout <Checkout|nil> :order <Order|nil>}
```
- events: `:catalog/loaded`, `:cart/add`, `:cart/update-qty`, `:cart/remove`, `:cart/clear`, `:checkout/start`, `:checkout/set-stage`, `:checkout/set-field`, `:checkout/next`, `:checkout/prev`.
- subs: `:catalog/catalog`, `:catalog/products`, `:cart/cart`, `:cart/totals`, `:cart/count`, `:checkout/checkout`, `:order/current`.
- App code MUST stay within the 7-fn portable subset (no effects/cofx/interceptors/chaining). Host side-effects (payment/store) wrap dispatch.

## mise.views (pure hiccup on shitsuke.components)

Stable `mise__*` classes via `shitsuke.style/class-name`. `data-act` convention for interaction.
- `(price p opts?)`, `(qty-stepper qty opts?)`, `(product-card product opts?)`, `(cart-line line opts?)`, `(cart-summary totals opts?)`, `(checkout-form checkout opts?)`, `(order-confirmation order opts?)`.

## mise.ssr

- `(sample-catalog)`, `(sample-db view?)`, `(root db)` → hiccup, `(root-html db?)` → HTML string (with shitsuke `:root` token vars inlined).

## Styling contract

Consumer `:pages` build adds `mise.views` to shadow-css `:include`; `mise__*` classes get scoped CSS. `:root` vars from `shitsuke.style/root-css`. Views carry no inline visual CSS.
