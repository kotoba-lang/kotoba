//! Social Capital ledger — re-exported from `kotoba-query` (the engine home), plus
//! the server-side **L6 settlement bridge** to the live mKOTO wallet.
//!
//! The ledger/MV/mint/retainer implementation lives in [`kotoba_query::social`]
//! (ADR-2606082100) so the reducer and the ledger share one decay primitive; the
//! `kotoba_server::social::*` path re-exports it. This module adds the one piece
//! that is server-specific: writing settled retainer credits into the persisted
//! [`crate::econ::Econ`] balance store.
//!
//! See `docs/SOCIAL-CAPITAL-LEDGER.md` + `docs/MISHMAR-OBSERVATION.md`.

pub use kotoba_query::social::*;

use crate::econ::Econ;
// `RetainerCredit` is in scope via the `pub use kotoba_query::social::*` above.

/// Apply an L6 retainer settlement to the live, persisted mKOTO wallet
/// ([`Econ`]): credit each pinner's balance by its aggregated retainer. mKOTO is
/// internal accounting — `Econ::credit` only adds (non-transferable), and the
/// balance is persisted, so earned retainer survives restarts. Returns the total
/// mKOTO credited.
///
/// Pinners are keyed by their DID **CID string** (`KotobaCid::to_string`).
/// Reconciling that with CACAO-writer DID-string balance keys (a `did ↔ cid`
/// bridge) is a follow-up; until then retainer balances live under the pinner CID.
pub async fn settle_retainer_to_econ(econ: &Econ, credits: &[RetainerCredit]) -> i64 {
    let mut total: i64 = 0;
    for c in credits {
        if c.mkoto <= 0 {
            continue;
        }
        econ.credit(&c.pinner_did.to_string(), c.mkoto).await;
        total = total.saturating_add(c.mkoto);
    }
    total
}

use kotoba_query::datom::Datom;

/// The I/O boundary for the social mint job (#3): a source that **observes** an
/// epoch's validated social inputs. Real implementations call the anchor-chain
/// `eth_getLogs` (terminal ClaimStakeEscrow state + slashes), the CitationLedger,
/// and the KaizenObserver wellbecoming feed — all read-only (kotoba stays
/// read+verify). This trait keeps `run_social_mint` testable with a fake source
/// and isolates the (not-yet-wired) network I/O from the deterministic pipeline.
pub trait SocialObservationSource {
    fn disclosures(&self, epoch: u64) -> Vec<ObservedDisclosure>;
    fn wellbecomings(&self, epoch: u64) -> Vec<ObservedWellbecoming>;
    fn falsifications(&self, epoch: u64) -> Vec<Falsification>;
}

/// Server-side mint job orchestrator: observe an epoch via `src`, run the
/// deterministic [`SocialMintJob`] pipeline (validate → weigh → emit), and return
/// the `social/mint|burn` Datoms to commit. The caller transacts these into the
/// Datom log — which feeds `SocialCapitalView` (the rest of the loop).
pub fn run_social_mint(
    job: &SocialMintJob,
    src: &dyn SocialObservationSource,
    epoch: u64,
) -> Vec<Datom> {
    job.run_epoch(
        &src.disclosures(epoch),
        &src.wellbecomings(epoch),
        &src.falsifications(epoch),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use kotoba_core::cid::KotobaCid;

    fn did(s: &str) -> KotobaCid {
        KotobaCid::from_bytes(s.as_bytes())
    }

    #[tokio::test]
    async fn settlement_credits_persisted_econ_balances() {
        let econ = Econ::from_env("did:key:operator".to_string());
        let peggy = did("did:key:peggy");
        let quinn = did("did:key:quinn");
        let credits = vec![
            RetainerCredit {
                pinner_did: peggy.clone(),
                mkoto: 963_768,
            },
            RetainerCredit {
                pinner_did: quinn.clone(),
                mkoto: 36_231,
            },
        ];

        let total = settle_retainer_to_econ(&econ, &credits).await;

        assert_eq!(total, 1_000_000 - 1); // matches the example's settled total
        assert_eq!(econ.balance(&peggy.to_string()).await, 963_768);
        assert_eq!(econ.balance(&quinn.to_string()).await, 36_231);
    }

    /// Fake observation source — stands in for the (not-yet-wired) anchor-chain /
    /// CitationLedger / KaizenObserver I/O so the orchestrator is testable.
    struct FakeSource {
        a: KotobaCid,
    }
    impl SocialObservationSource for FakeSource {
        fn disclosures(&self, epoch: u64) -> Vec<ObservedDisclosure> {
            vec![
                ObservedDisclosure {
                    did: self.a.clone(),
                    epoch,
                    n_validated: 2,
                    citation_hits: 5,
                    terminal_honest: true,
                    witness_quorum_met: true,
                },
                // unvalidated → must be dropped by the pipeline
                ObservedDisclosure {
                    did: did("did:key:spam"),
                    epoch,
                    n_validated: 99,
                    citation_hits: 0,
                    terminal_honest: false,
                    witness_quorum_met: false,
                },
            ]
        }
        fn wellbecomings(&self, epoch: u64) -> Vec<ObservedWellbecoming> {
            vec![ObservedWellbecoming {
                did: self.a.clone(),
                epoch,
                delta: 5,
                council_attested: true,
            }]
        }
        fn falsifications(&self, _epoch: u64) -> Vec<Falsification> {
            vec![]
        }
    }

    #[test]
    fn run_social_mint_observes_validates_and_emits() {
        let a = did("did:key:a");
        let job = SocialMintJob::new(MintParams::default(), did("g:social"));
        let src = FakeSource { a: a.clone() };
        let datoms = run_social_mint(&job, &src, 0);
        // a's valid disclosure (2.5) + wellbecoming (10.0) emit; spam dropped.
        assert_eq!(datoms.len(), 2);
        assert!(datoms.iter().all(|d| d.e == a)); // spam DID never emitted
    }

    #[tokio::test]
    async fn settlement_is_additive_and_skips_nonpositive() {
        let econ = Econ::from_env("did:key:operator".to_string());
        let p = did("did:key:p");
        // first settlement
        settle_retainer_to_econ(
            &econ,
            &[RetainerCredit {
                pinner_did: p.clone(),
                mkoto: 100,
            }],
        )
        .await;
        // second settlement accumulates; a zero credit is skipped (no row churn)
        let total = settle_retainer_to_econ(
            &econ,
            &[
                RetainerCredit {
                    pinner_did: p.clone(),
                    mkoto: 50,
                },
                RetainerCredit {
                    pinner_did: did("did:key:zero"),
                    mkoto: 0,
                },
            ],
        )
        .await;
        assert_eq!(total, 50); // only the positive credit counts toward total
        assert_eq!(econ.balance(&p.to_string()).await, 150); // 100 + 50 accumulated
        assert_eq!(econ.balance(&did("did:key:zero").to_string()).await, 0);
    }
}
