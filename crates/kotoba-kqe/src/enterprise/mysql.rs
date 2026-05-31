//! MySQL / MariaDB SQL dialect compiler.
//!
//! Uses `sqlparser::dialect::MySqlDialect`, which natively handles
//! backtick-quoted identifiers, the `LIMIT offset, count` comma form, and
//! `# ...` line comments — so the preprocessor stays minimal.
//!
//! `LIMIT` / `OFFSET` / `ORDER BY` are extracted into `PostProcess` by
//! `SchemaBasedSqlCompiler` (shared with every other dialect).
//!
//! # Supported MySQL-specific features
//!
//! | Feature | Handling |
//! |---------|----------|
//! | backtick identifiers `` `col` `` | parsed natively by `MySqlDialect` |
//! | `LIMIT offset, count` | parsed natively → `PostProcess::{offset,limit}` |
//! | `LIMIT count OFFSET offset` | → `PostProcess::{limit,offset}` |
//! | `STRAIGHT_JOIN` | → rewritten to `JOIN` (planner hint, no Datalog effect) |
//! | `OVER (...)` window functions | → `EnterpriseFeature::OlapWindow` |

use sqlparser::dialect::MySqlDialect as SqlparserMySql;

use super::{
    sql_base::SchemaBasedSqlCompiler, CompiledEnterpriseQuery, EnterpriseDialect, EnterpriseFeature,
};
use crate::schema::SchemaMap;

pub struct MySqlDialect;

impl EnterpriseDialect for MySqlDialect {
    fn dialect_name(&self) -> &'static str {
        "mysql"
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

        let prepped = preprocess_mysql(query);

        let (program, pp) =
            SchemaBasedSqlCompiler::compile(&prepped, &SqlparserMySql {}, schema, output)?;

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

fn preprocess_mysql(sql: &str) -> String {
    // STRAIGHT_JOIN is a MySQL planner hint forcing join order; Kotoba's Datalog
    // engine reorders freely, so it is semantically a plain INNER JOIN.
    sql.replace("STRAIGHT_JOIN", "JOIN")
        .replace("straight_join", "JOIN")
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
    fn standard_mysql_select() {
        let mut schema = SchemaMap::new();
        schema.add(
            "users",
            TableSchema::new("id")
                .with_attr(AttrDef::scalar("name", "users"))
                .with_attr(AttrDef::scalar("status", "users")),
        );

        let result = MySqlDialect
            .compile(
                "SELECT u.id, u.name FROM users u WHERE u.status = 'active'",
                &schema,
                "active_users",
            )
            .unwrap();
        assert_eq!(result.dialect, "mysql");

        let input = vec![
            fact("users/name", "u1", "alice"),
            fact("users/status", "u1", "active"),
            fact("users/name", "u2", "bob"),
            fact("users/status", "u2", "banned"),
        ];
        let derived = result.program.evaluate_delta(&input);
        assert!(has(&derived, "active_users", "u1", "alice"));
        assert!(!has(&derived, "active_users", "u2", "bob"));
    }

    #[test]
    fn backtick_identifiers_parse() {
        let mut schema = SchemaMap::new();
        schema.add(
            "orders",
            TableSchema::new("id").with_attr(AttrDef::scalar("state", "orders")),
        );

        let result = MySqlDialect
            .compile(
                "SELECT `o`.`id`, `o`.`state` FROM `orders` `o` WHERE `o`.`state` = 'paid'",
                &schema,
                "out",
            )
            .unwrap();
        let input = vec![fact("orders/state", "o1", "paid")];
        let derived = result.program.evaluate_delta(&input);
        assert!(has(&derived, "out", "o1", "paid"));
    }

    #[test]
    fn limit_comma_offset_form() {
        // MySQL legacy `LIMIT offset, count` → offset=5, limit=10
        let mut schema = SchemaMap::new();
        schema.add(
            "logs",
            TableSchema::new("id").with_attr(AttrDef::scalar("msg", "logs")),
        );

        let result = MySqlDialect
            .compile("SELECT l.id, l.msg FROM logs l LIMIT 5, 10", &schema, "out")
            .unwrap();
        assert_eq!(result.post_process.offset, Some(5));
        assert_eq!(result.post_process.limit, Some(10));
    }

    #[test]
    fn limit_offset_keyword_form() {
        let mut schema = SchemaMap::new();
        schema.add(
            "logs",
            TableSchema::new("id").with_attr(AttrDef::scalar("msg", "logs")),
        );

        let result = MySqlDialect
            .compile(
                "SELECT l.id, l.msg FROM logs l LIMIT 10 OFFSET 5",
                &schema,
                "out",
            )
            .unwrap();
        assert_eq!(result.post_process.limit, Some(10));
        assert_eq!(result.post_process.offset, Some(5));
    }

    #[test]
    fn straight_join_rewritten() {
        let mut schema = SchemaMap::new();
        schema.add(
            "a",
            TableSchema::new("id").with_attr(AttrDef::scalar("ref", "a")),
        );
        schema.add(
            "b",
            TableSchema::new("id").with_attr(AttrDef::scalar("val", "b")),
        );
        // Should compile cleanly with the hint stripped.
        let result = MySqlDialect.compile(
            "SELECT a.id, b.val FROM a STRAIGHT_JOIN b ON a.ref = b.id",
            &schema,
            "out",
        );
        assert!(
            result.is_ok(),
            "STRAIGHT_JOIN should compile: {:?}",
            result.err()
        );
    }
}
