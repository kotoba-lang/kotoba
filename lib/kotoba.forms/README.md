# forms

[![CI](https://github.com/kotoba-lang/forms/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/forms/actions/workflows/ci.yml)

Portable CLJC model for kotoba-lang/forms.

Pages editor: https://kotoba-lang.github.io/forms/

The Pages UI is local to kotoba-lang and does not redirect to external hosts.

## Wire

`forms.wire/form-envelope` wraps a form in the shared Kotoba office envelope,
using `application/json` and the `:forms/form` resource kind — the same
arrangement `sheets` and `docs` have. Forms was the one without it, because
`transit.core/office-resource-kinds` is closed and did not list `:forms/form`
until now.

`read-form-envelope` gives the payload back as plain JSON — string keys,
`"text"` where `:text` went in — because that is what the current `transit`
wire carries. `rehydrate-form` turns it back into a form, and
`form-of-envelope` does both in one step.

**Anything that validates has to rehydrate first.** `forms.validate` reads
`:forms/fields`, which on a projected payload is `nil`, so it iterates
nothing and reports no problems — a broken form comes back "valid" rather
than coming back wrong. There is a test for exactly that.

## Responses as a table

`forms.responses` turns the map-per-response a form collects into the grid
everyone actually reads it as — one row per response, one column per
question:

```clojure
(r/rows-with-header form submissions)   ; header row, then one row each
(r/table form submissions)              ; {:columns [...] :rows [...]}
```

**Columns come from the form, not from the answers.** Deriving them from the
keys present in the responses is the obvious implementation and it loses a
question nobody answered, and gives two responses with different keys rows of
different widths — values sliding sideways under headings that belong to
other questions. A blank is information; a shifted column is a lie.

Answers to a question since deleted from the form are kept as trailing
columns rather than dropped, because dropping them discards data somebody
gave you.

It returns plain data and stops. Turning it into a workbook needs `sheets`
too, so that belongs to whoever already has both.

## Test

```bash
kbb -M:test                                                       # JVM
kbb --backend sci --classpath "src:test:$(kbb -Spath)" scripts/test-cljs.cljk   # ClojureScript
```
