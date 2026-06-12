//! PostgreSQL SQL dialect compiler.
//!
//! Uses `sqlparser::dialect::PostgreSqlDialect`, which natively handles
//! `LIMIT count OFFSET offset`, `FETCH FIRST N ROWS ONLY`, dollar-quoted
//! strings, and `::` cast expressions — so the preprocessor stays minimal.
//!
//! `LIMIT` / `OFFSET` / `FETCH` / `ORDER BY` are extracted into `PostProcess`
//! by `SchemaBasedSqlCompiler` (shared with every other dialect).
//!
//! NOTE: this compiles **PostgreSQL dialect TEXT → Datalog**. It is unrelated
//! to PostgreSQL *wire-protocol* compatibility, which Kotoba deliberately does
//! not implement (see ADR-2605240001 §2 OUT-scope).
//!
//! # Supported PostgreSQL-specific features
//!
//! | Feature | Handling |
//! |---------|----------|
//! | `LIMIT n OFFSET m` | → `PostProcess::{limit,offset}` |
//! | `FETCH FIRST N ROWS ONLY` | → `PostProcess::limit` |
//! | `ILIKE` | → rewritten to `LIKE` (Kotoba CID space is case-sensitive) |
//! | `LIMIT ALL` | → stripped (no row cap) |
//! | `OVER (...)` window functions | → `EnterpriseFeature::OlapWindow` |

use sqlparser::dialect::PostgreSqlDialect as SqlparserPostgres;

use super::{
    sql_base::SchemaBasedSqlCompiler, CompiledEnterpriseQuery, EnterpriseDialect, EnterpriseFeature,
};
use crate::schema::SchemaMap;

pub struct PostgreSqlDialect;

impl EnterpriseDialect for PostgreSqlDialect {
    fn dialect_name(&self) -> &'static str {
        "postgresql"
    }

    fn compile(
        &self,
        query: &str,
        schema: &SchemaMap,
        output: &str,
    ) -> anyhow::Result<CompiledEnterpriseQuery> {
        let mut features = Vec::new();
        let upper = query.to_uppercase();

        if upper.contains("OVER (") || upper.contains("OVER(") {
            features.push(EnterpriseFeature::OlapWindow);
        }

        let prepped = preprocess_postgres(query);

        let (program, pp) =
            SchemaBasedSqlCompiler::compile(&prepped, &SqlparserPostgres {}, schema, output)?;

        Ok(CompiledEnterpriseQuery {
            program,
            output_relation: output.to_string(),
            dialect: self.dialect_name(),
            features,
            post_process: pp,
        })
    }
}

// ── Preprocessor ─────────────────────────────────────────────────────────────

fn preprocess_postgres(sql: &str) -> String {
    let mut s = sql.to_string();

    // ILIKE → LIKE (case-insensitive match has no analogue in the case-sensitive
    // CID space; approximate with LIKE — same precedent as the Snowflake dialect).
    s = s.replace("ILIKE", "LIKE").replace("ilike", "LIKE");

    // `LIMIT ALL` means "no limit" in PostgreSQL; drop it so the parser does not
    // choke and no spurious PostProcess::limit is produced.
    s = s.replace("LIMIT ALL", "").replace("limit all", "");

    s
}

// ── Tests ─────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use crate::schema::{AttrDef, SchemaMap, TableSchema};
    use crate::{
        datom::{Datom, Value},
        delta::Delta,
    };
    use kotoba_core::cid::KotobaCid;

    fn cid(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }
    fn fact(pred: &str, s: &str, o: &str) -> Delta {
        Delta::assert_datom(Datom::assert(
            cid(s),
            pred.to_string(),
            Value::Cid(cid(o)),
            cid("g"),
        ))
    }
    fn has(d: &[Delta], pred: &str, s: &str, o: &str) -> bool {
        d.iter().any(|x| {
            x.attribute() == pred
                && x.entity() == &cid(s)
                && matches!(x.value(), Value::Cid(c) if *c == cid(o))
        })
    }

    #[test]
    fn standard_postgres_select() {
        let mut schema = SchemaMap::new();
        schema.add(
            "people",
            TableSchema::new("id")
                .with_attr(AttrDef::scalar("name", "people"))
                .with_attr(AttrDef::scalar("role", "people")),
        );

        let result = PostgreSqlDialect
            .compile(
                "SELECT p.id, p.name FROM people p WHERE p.role = 'admin'",
                &schema,
                "admins",
            )
            .unwrap();
        assert_eq!(result.dialect, "postgresql");

        let input = vec![
            fact("people/name", "p1", "alice"),
            fact("people/role", "p1", "admin"),
            fact("people/name", "p2", "bob"),
            fact("people/role", "p2", "user"),
        ];
        let derived = result.program.evaluate_delta(&input);
        assert!(has(&derived, "admins", "p1", "alice"));
        assert!(!has(&derived, "admins", "p2", "bob"));
    }

    #[test]
    fn limit_offset_form() {
        let mut schema = SchemaMap::new();
        schema.add(
            "events",
            TableSchema::new("id").with_attr(AttrDef::scalar("kind", "events")),
        );

        let result = PostgreSqlDialect
            .compile(
                "SELECT e.id, e.kind FROM events e LIMIT 25 OFFSET 50",
                &schema,
                "out",
            )
            .unwrap();
        assert_eq!(result.post_process.limit, Some(25));
        assert_eq!(result.post_process.offset, Some(50));
    }

    #[test]
    fn fetch_first_limit() {
        let mut schema = SchemaMap::new();
        schema.add(
            "events",
            TableSchema::new("id").with_attr(AttrDef::scalar("kind", "events")),
        );

        let result = PostgreSqlDialect
            .compile(
                "SELECT e.id, e.kind FROM events e FETCH FIRST 7 ROWS ONLY",
                &schema,
                "out",
            )
            .unwrap();
        assert_eq!(result.post_process.limit, Some(7));
    }

    #[test]
    fn ilike_is_rejected_fail_loud() {
        // ILIKE is preprocessed to LIKE, but LIKE is not a supported WHERE filter
        // in the CID-hashed object space — it must be rejected, not silently
        // dropped (which would return an unfiltered superset).
        assert_eq!(
            preprocess_postgres("WHERE x ILIKE 'a%'"),
            "WHERE x LIKE 'a%'"
        );

        let mut schema = SchemaMap::new();
        schema.add(
            "docs",
            TableSchema::new("id").with_attr(AttrDef::scalar("title", "docs")),
        );
        match PostgreSqlDialect.compile(
            "SELECT d.id, d.title FROM docs d WHERE d.title ILIKE 'report%'",
            &schema,
            "out",
        ) {
            Ok(_) => panic!("LIKE/ILIKE WHERE must be rejected fail-loud"),
            Err(e) => assert!(
                e.to_string().contains("unsupported WHERE"),
                "unexpected error: {e}"
            ),
        }
    }

    #[test]
    fn limit_all_stripped() {
        let mut schema = SchemaMap::new();
        schema.add(
            "events",
            TableSchema::new("id").with_attr(AttrDef::scalar("kind", "events")),
        );

        let result = PostgreSqlDialect
            .compile(
                "SELECT e.id, e.kind FROM events e LIMIT ALL",
                &schema,
                "out",
            )
            .unwrap();
        assert_eq!(result.post_process.limit, None);
    }
}
