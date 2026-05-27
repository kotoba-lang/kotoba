//! ashiba.gftd.ai Lean BMC — kotoba Quad storage + Datalog coverage scoring
//!
//! This example encodes the ashiba Lean BMC as kotoba Quads, then runs
//! a DatalogProgram to compute coverage % and per-block maturity scores.
//!
//! Data source: `60-apps/ai-gftd-project-jp-ashiba/docs/bmc/ashiba-lean-bmc-v13.toml`
//! Rules source: `60-apps/ai-gftd-project-jp-ashiba/docs/bmc/coverage.dl`

use anyhow::Result;
use kotoba_core::cid::KotobaCid;
use kotoba_kqe::{
    datalog::{Atom, BodyLiteral, DatalogProgram, DatalogRule, Term},
    delta::Delta,
    quad::{Quad, QuadObject},
};
use kotoba_store::MemoryBlockStore;
use std::sync::Arc;

// ─────────────────────────────────────────────────────────────────────────────
// Lean BMC blocks (Lean Canvas hybrid, 9 blocks)
// ─────────────────────────────────────────────────────────────────────────────

const BMC_BLOCKS: &[(&str, i64)] = &[
    ("problem",           5),
    ("customer_segments", 5),
    ("uvp",               5),
    ("solution",          4),
    ("channels",          4),
    ("revenue",           4),
    ("cost_structure",    3),
    ("key_metrics",       4),
    ("unfair_advantage",  5),
];

// ─────────────────────────────────────────────────────────────────────────────
// Lean hypotheses: (entry_id, block, hypothesis_text, validated)
// ─────────────────────────────────────────────────────────────────────────────

const HYPOTHESES: &[(&str, &str, &str, bool)] = &[
    // problem
    ("p_domestic",       "problem",           "国内ペイン普遍的 (stable)", true),
    ("p_korea_taiwan",   "problem",           "韓国+台湾 同一ペイン 91% (n=30社) stable", true),
    ("p_sea_survey",     "problem",           "東南アジア 同一ペイン調査 → IPO TAM 拡張", false),
    // customer_segments
    ("cs_enterprise5",   "customer_segments", "ゼネコン 5社 Enterprise ARR ¥5.4M stable", true),
    ("cs_korea_pilot",   "customer_segments", "韓국 22社 pilot 2027-03-01 正式開始", true),
    ("cs_taiwan_pipe",   "customer_segments", "台湾 10社 pipeline → 2027-Q3 pilot", false),
    // uvp
    ("uvp_v3_live",      "uvp",               "v3 AI 本番稼働 2027-02-01 精度 88.3%", true),
    ("uvp_jis_mandatory","uvp",               "JIS A 8951:2026 義務化 仕様権保有 stable", true),
    ("uvp_korea_std",    "uvp",               "韓国 KS F 改訂 → ashiba API 義務化仮説", false),
    // solution
    ("sol_v3_live",      "solution",          "v3 AI 本番稼働 + 成約率 97.8%", true),
    ("sol_korea_stable", "solution",          "韓국 API 本番 SLA 99.7% 安定稼働", true),
    ("sol_taiwan_api",   "solution",          "台湾版 API TWD 決済 設計中", false),
    ("sol_v4_video",     "solution",          "v4 AI 動画 → 施工品質 audit PoC", false),
    // channels
    ("ch_korea_full",    "channels",          "韓国 현대건설 full expansion 22→100社 2027-Q4", true),
    ("ch_seo_2000",      "channels",          "SEO organic 2,047/月 Month 9 達成", true),
    ("ch_taiwan_partner","channels",          "台湾 BizDev パートナー 1社 2027-Q3", false),
    ("ch_sea_explore",   "channels",          "タイ BizDev 初期探索 (IPO TAM 用)", false),
    // revenue
    ("r_gmv_100m",       "revenue",           "GMV ¥100M/月 Month 12 (2027-Q1) 達成仮説", false),
    ("r_enterprise_756", "revenue",           "Enterprise ARR ¥7.56M stable", true),
    ("r_korea_gmv",      "revenue",           "韓国 pilot GMV ¥8M/月 2027-Q2 寄与仮説", false),
    ("r_enterprise_12m", "revenue",           "Enterprise ARR ¥12M (8社, 2027-Q4)", false),
    // cost_structure
    ("cs_korea_stable",  "cost_structure",    "주식회사 아시바코리아 5名 安定稼働", true),
    ("cs_auditor",       "cost_structure",    "IPO 監査法人 Big4 契約 2027-Q4", false),
    ("cs_underwriter",   "cost_structure",    "IPO 主幹事証券 選定 2027-Q4", false),
    ("cs_team_45",       "cost_structure",    "45名体制 + 台湾 5名 runway 24ヶ月", false),
    // key_metrics
    ("km_nrr_128",       "key_metrics",       "NRR 128% stable", true),
    ("km_d365",          "key_metrics",       "D365 実測 > 30% (2027-05-01)", false),
    ("km_ipo_kpi",       "key_metrics",       "IPO KPI ダッシュボード 監査法人 承認", false),
    // unfair_advantage
    ("ua_jis_mandatory", "unfair_advantage",  "JIS 義務化 仕様権保有 参入コスト ∞ stable", true),
    ("ua_did_4800",      "unfair_advantage",  "DID 4,800件 相関 0.81 + 韓국 DID 加速", true),
    ("ua_v3_ip",         "unfair_advantage",  "v3 AI 特許出願 日本+韓国+PCT 2027-Q2", false),
];

// ─────────────────────────────────────────────────────────────────────────────
// CID helper
// ─────────────────────────────────────────────────────────────────────────────

fn cid(s: &str) -> KotobaCid { KotobaCid::from_bytes(s.as_bytes()) }

fn graph_cid() -> KotobaCid { cid("bmc:ashiba:v13") }

fn quad(subject: &str, predicate: &str, object: QuadObject) -> Quad {
    Quad { graph: graph_cid(), subject: cid(subject), predicate: predicate.to_string(), object }
}

// ─────────────────────────────────────────────────────────────────────────────
// Build BMC fact deltas
// ─────────────────────────────────────────────────────────────────────────────

fn build_bmc_facts() -> Vec<Delta> {
    let mut deltas = Vec::new();

    // bmc root
    deltas.push(Delta::assert(quad(
        "bmc:ashiba", "bmc/version", QuadObject::Text("v13".into()),
    )));
    deltas.push(Delta::assert(quad(
        "bmc:ashiba", "bmc/product", QuadObject::Text("ashiba.gftd.ai".into()),
    )));
    deltas.push(Delta::assert(quad(
        "bmc:ashiba", "bmc/model", QuadObject::Text("lean-canvas-hybrid".into()),
    )));

    // blocks: bmc/block(bmc_cid, block_name_cid) + bmc/maturity(block_cid, int)
    for (block_name, maturity) in BMC_BLOCKS {
        let block_id = format!("bmc:ashiba:block:{block_name}");

        // bmc/block relation: bmc_root → block_cid (using object as text label)
        deltas.push(Delta::assert(quad(
            "bmc:ashiba",
            "bmc/block",
            QuadObject::Cid(cid(&block_id)),
        )));

        // bmc/block_name: block_cid → name text
        deltas.push(Delta::assert(quad(
            &block_id,
            "bmc/block_name",
            QuadObject::Text(block_name.to_string()),
        )));

        // bmc/maturity: block_cid → integer
        deltas.push(Delta::assert(quad(
            &block_id,
            "bmc/maturity",
            QuadObject::Integer(*maturity),
        )));

        // each block has at least one entry (coverage = all 9 filled)
        let entry_id = format!("bmc:ashiba:entry:{block_name}:default");
        deltas.push(Delta::assert(quad(
            &entry_id,
            "entry/block",
            QuadObject::Cid(cid(&block_id)),
        )));
    }

    // hypotheses
    for (entry_id, block_name, hypothesis, validated) in HYPOTHESES {
        let full_entry_id = format!("bmc:ashiba:entry:{block_name}:{entry_id}");
        let block_id = format!("bmc:ashiba:block:{block_name}");

        deltas.push(Delta::assert(quad(
            &full_entry_id,
            "entry/block",
            QuadObject::Cid(cid(&block_id)),
        )));
        deltas.push(Delta::assert(quad(
            &full_entry_id,
            "bmc/hypothesis",
            QuadObject::Text(hypothesis.to_string()),
        )));
        deltas.push(Delta::assert(quad(
            &full_entry_id,
            "bmc/validated",
            QuadObject::Bool(*validated),
        )));
    }

    deltas
}

// ─────────────────────────────────────────────────────────────────────────────
// Build coverage / maturity Datalog program
// ─────────────────────────────────────────────────────────────────────────────
//
// Datalog atoms are binary: (subject_cid, object_cid).
// We use kotoba-kqe's string-keyed relations where the predicate is the
// relation name, and subject/object are CIDs derived from the quad.
//
// Rules implemented:
//   covered(Block) :- entry/block(_, Block).
//   at_risk(Entry) :- bmc/hypothesis(Entry, _), bmc/validated(Entry, false).
//   below_target(Block) :- bmc/maturity(Block, M), M < 3.

fn build_coverage_program() -> DatalogProgram {
    let mut prog = DatalogProgram::new();

    // covered(Block) :- entry/block(Entry, Block).
    // i.e., for all (Entry, Block) in entry/block relation → assert covered(Block)
    prog.add_rule(DatalogRule {
        head: Atom {
            relation: "covered".into(),
            args: vec![Term::Variable("Block".into()), Term::Variable("Block".into())],
        },
        body: vec![BodyLiteral::Positive(Atom {
            relation: "entry/block".into(),
            args: vec![Term::Variable("Entry".into()), Term::Variable("Block".into())],
        })],
    });

    // at_risk(Entry) :- bmc/hypothesis(Entry, Hyp), bmc/validated(Entry, False)
    // (simplified: if entry has a hypothesis quad, it's at risk until validated=true)
    prog.add_rule(DatalogRule {
        head: Atom {
            relation: "at_risk".into(),
            args: vec![Term::Variable("Entry".into()), Term::Variable("Entry".into())],
        },
        body: vec![
            BodyLiteral::Positive(Atom {
                relation: "bmc/hypothesis".into(),
                args: vec![Term::Variable("Entry".into()), Term::Variable("_H".into())],
            }),
            BodyLiteral::Positive(Atom {
                relation: "bmc/validated".into(),
                args: vec![
                    Term::Variable("Entry".into()),
                    Term::Constant(cid_label_for_bool(false)),
                ],
            }),
        ],
    });

    prog
}

fn cid_label_for_bool(b: bool) -> String {
    // QuadObject::Bool serializes to cid_of_str("true"/"false") in evaluate_delta
    if b { "true".into() } else { "false".into() }
}

// ─────────────────────────────────────────────────────────────────────────────
// Scoring: compute directly from BMC_BLOCKS (no Datalog needed for integers)
// ─────────────────────────────────────────────────────────────────────────────

fn print_score_report(derived_covered: usize, derived_at_risk: usize) {
    let total = BMC_BLOCKS.len();
    let coverage_pct = (derived_covered * 100) / total;
    let maturity_sum: i64 = BMC_BLOCKS.iter().map(|(_, m)| m).sum();
    let maturity_avg = maturity_sum as f64 / total as f64;

    let mut below_target: Vec<&str> = Vec::new();
    for (block, maturity) in BMC_BLOCKS {
        if *maturity < 3 { below_target.push(block); }
    }

    println!("╔══════════════════════════════════════════════════════════╗");
    println!("║     ashiba.gftd.ai Lean BMC — kotoba Scoring Report      ║");
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  Iteration : 13 (2026-05-27) [IPO 準備フェーズ Month 1] ║");
    println!("║  Model     : Lean Canvas Hybrid (9 blocks)               ║");
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  Coverage  : {derived_covered}/{total} blocks = {coverage_pct}%                       ║");
    println!("║  Maturity  : {maturity_avg:.1} / 5.0 (avg)                          ║");
    println!("║  At-Risk   : {derived_at_risk} unvalidated hypotheses                 ║");
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  Per-Block Maturity                                       ║");
    for (block, m) in BMC_BLOCKS {
        let bar = "█".repeat(*m as usize);
        let gap = "░".repeat((5 - m) as usize);
        let flag = if *m < 3 { " ← next" } else { "       " };
        println!("║  {block:<22} [{bar}{gap}] {m}/5{flag}║");
    }
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  Blocks below target (< 3):                              ║");
    for b in &below_target {
        println!("║    · {b:<52}║");
    }
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  Riskiest Assumptions (prioritised)                      ║");
    println!("║    1. GMV ¥100M/月 Month 12 — 韓국 pilot GMV 寄与が鍵   ║");
    println!("║    2. 監査法人 + 主幹事 選定 (2027-Q4) — Big4 受諾確度  ║");
    println!("║    3. D365 実測 > 30% (2027-05-01) — 初回実計測          ║");
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  v3 live 88.3% / GMV ¥75M→¥100M / DID 4,800件 / NRR128%║");
    println!("║  韓국 pilot 2027-03-01 / JIS 義務化 / ARR ¥7.56M→¥12M  ║");
    println!("╠══════════════════════════════════════════════════════════╣");
    println!("║  IPO 準備フェーズ — 2028 上場 target                     ║");
    println!("║    · GMV ¥100M/月 (Month 12 / 2027-Q1) 確認             ║");
    println!("║    · 韓국 pilot → 本格展開 100社 (2027-Q4)              ║");
    println!("║    · 台湾 pilot 開始 (2027-Q3)                          ║");
    println!("║    · 監査法人 + 主幹事 選定 + IPO KPI 承認 (2027-Q4)    ║");
    println!("╚══════════════════════════════════════════════════════════╝");
}

// ─────────────────────────────────────────────────────────────────────────────
// main
// ─────────────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() -> Result<()> {
    tracing_subscriber::fmt::init();

    let _store = Arc::new(MemoryBlockStore::new());

    // 1. Build fact deltas from BMC data
    let facts = build_bmc_facts();
    println!("Loaded {} BMC fact deltas into kotoba Quad store", facts.len());

    // 2. Build and run Datalog coverage program
    let prog = build_coverage_program();
    let derived = prog.evaluate_delta(&facts);

    // 3. Count derived facts
    let covered_count = derived.iter()
        .filter(|d| d.quad.predicate == "covered" && d.is_assert())
        .count();
    // Deduplicate by subject CID (one block may derive covered multiple times)
    let covered_blocks: std::collections::HashSet<_> = derived.iter()
        .filter(|d| d.quad.predicate == "covered" && d.is_assert())
        .map(|d| d.quad.subject.clone())
        .collect();

    let at_risk_entries: std::collections::HashSet<_> = derived.iter()
        .filter(|d| d.quad.predicate == "at_risk" && d.is_assert())
        .map(|d| d.quad.subject.clone())
        .collect();

    println!("Datalog derived {} facts total", derived.len());
    println!("  covered blocks : {}", covered_blocks.len());
    println!("  at-risk entries: {}", at_risk_entries.len());

    // 4. Print scored report
    println!();
    print_score_report(covered_blocks.len(), at_risk_entries.len());

    Ok(())
}
