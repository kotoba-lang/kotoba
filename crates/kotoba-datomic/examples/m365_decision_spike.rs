//! Feasibility spike (ADR-0013): load a real gftdcojp M365 `decision` fact into
//! kotoba-datomic and query it with Datalog — proving the M365 fact layer runs
//! on kotoba instead of JVM Datomic Local.
use kotoba_datomic::{q, Connection};
use kotoba_edn::parse;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let conn = Connection::new();

    // The exact decision the manimani `decide` command wrote to decisions.jsonl
    // (TMI 請求スレッド, gemma4 が reply 提案 → ユーザー確定), as a kotoba datom tx.
    let tx = parse(
        r#"[{:db/id "d1"
                        :gftd.decision/id "<OS3PR01MB7665...@OS3PR01MB7665.jpnprd01.prod.outlook.com>"
                        :gftd.decision/policy :reply
                        :gftd.decision/at "2026-06-13T04:52:31Z"
                        :gftd.decision/note "支払いに関する具体的な質問であり、丁寧な返信を行うべき。"}]"#,
    )?;
    let report = conn.transact(tx).await?;
    println!(
        "transacted {} datoms into kotoba-datomic",
        report.tx_data.len()
    );

    // :decisions/ledger view (views.edn), kotoba map form.
    let rows = q(
        parse(
            r#"{:find [?policy ?at ?note]
                  :where [[?d :gftd.decision/policy ?policy]
                          [?d :gftd.decision/at ?at]
                          [?d :gftd.decision/note ?note]]}"#,
        )?,
        &conn.db(),
        &[],
    )?;
    println!(
        "Datalog :decisions/ledger via kotoba-datomic::q => {} row(s)",
        rows.len()
    );
    for r in &rows {
        println!("  {:?}", r);
    }
    assert_eq!(rows.len(), 1, "expected the one committed decision");
    println!("OK — M365 decision queried through kotoba (not JVM Datomic)");
    Ok(())
}
