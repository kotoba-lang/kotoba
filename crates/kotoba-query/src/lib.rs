//! # kotoba-query — **KQE = Kotoba Query Engine**
//!
//! The Datalog query layer of KOTOBA: semi-naive Datalog evaluation
//! ([`datalog`]), the 4-index in-memory [`arrangement`] (EAVT/AEVT/AVET/VAET),
//! assert/retract [`delta`]s over the atomic [`datom::Datom`] 5-tuple
//! `(E, A, V, T, Added)`, materialized views ([`mv`]), and citation-royalty
//! accounting ([`citation`]).
//!
//! WASM guests reach this engine through the `kotoba:kais/kqe` WIT interface
//! (ASSERT 0x1 / RETRACT 0xD / QUERY 0x2 frames); KAIS = Kotoba Instruction
//! Set Architecture. Sibling engines: KSE (Kotoba Stream Engine,
//! `kotoba-vault`), KDHT (Kotoba DHT, `kotoba-dht`), KVM (Kotoba VM,
//! `kotoba-vm`).
pub mod arrangement;
pub mod citation;
pub mod cypher;
pub mod datalog;
pub mod datom;
pub mod delta;
pub mod enterprise;
pub mod evm_state;
pub mod keycodec;
pub mod mv;
pub mod quad;
pub mod schema;
pub mod social;
pub mod sql;

pub use arrangement::Arrangement;
pub use citation::{CitationLedger, DatomKey};
pub use cypher::{CompiledCypherMv, CypherCompiler};
pub use datalog::{object_value_cid, DatalogProgram, DatalogRule};
pub use datom::{
    Datom, DatomArrangement, DatomIndex, DatomIndexComponent, TensorDtype as DatomTensorDtype,
    Value,
};
pub use delta::Delta;
pub use enterprise::{
    BigQueryDialect, CompiledEnterpriseQuery, Db2Dialect, EnterpriseDialect, EnterpriseFeature,
    HanaDialect, HiveQlDialect, MdxDialect, MySqlDialect, OracleDialect, PostProcess,
    PostgreSqlDialect, PrestoDialect, SnowflakeDialect, TSqlDialect, TeradataDialect,
};
pub use mv::MaterializedView;
pub use quad::{LegacyQuad, LegacyQuadObject};
pub use schema::{AttrDef, AttrKind, SchemaMap, TableSchema};
pub use sql::{CompiledSqlMv, SqlMvCompiler};
