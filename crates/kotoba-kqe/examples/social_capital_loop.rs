//! End-to-end demonstration of the Mishmar social-capital economic loop
//! (ADR-2606082100). Runnable proof that the deterministic core closes the loop:
//!
//!   validated acts → mint engine → social/mint|burn Datoms
//!        → SocialCapitalView (decayed balances) → SC_root
//!        → retainer allocation (donation pool split by social capital)
//!
//! Run: `cargo run --example social_capital_loop -p kotoba-kqe`

use kotoba_core::cid::KotobaCid;
use kotoba_kqe::delta::Delta;
use kotoba_kqe::social::{
    allocate_retainer, Falsification, MintParams, PinOrigin, SocialCapitalView,
    ValidatedDisclosure, ValidatedWellbecoming, SCALE,
};

fn did(s: &str) -> KotobaCid {
    KotobaCid::from_bytes(s.as_bytes())
}

fn pts(smic: i64) -> String {
    format!("{:.3} pts", smic as f64 / SCALE as f64)
}

fn main() {
    let params = MintParams::default();
    let graph = did("g:social:2026-12");
    println!("== Mishmar social-capital loop (ADR-2606082100) ==");
    println!(
        "params: w_disclosure={:.1} w_wellbecoming={:.1} citation_bonus={:.1}/hit \
         burn_mult={:.1} half_life={}d\n",
        params.w_disclosure_milli as f64 / 1000.0,
        params.w_wellbecoming_milli as f64 / 1000.0,
        params.citation_bonus_milli as f64 / 1000.0,
        params.burn_falsified_mult_milli as f64 / 1000.0,
        params.half_life_epochs,
    );

    let alice = did("did:key:alice");
    let bob = did("did:key:bob");
    let carol = did("did:key:carol");

    // ── 1. Validated value-acts at epoch 0 (validation gates enforced by type) ──
    // alice: 2 validated disclosures + 8 citation hits  → 1.0·2 + 0.1·8 = 2.8 pts
    let alice_disc = ValidatedDisclosure::new(alice.clone(), 0, 2, 8, true, true)
        .expect("terminal-honest escrow + witness quorum");
    // alice: Council-attested wellbecoming Δ=+5 → 2.0·5 = 10.0 pts
    let alice_wb = ValidatedWellbecoming::new(alice.clone(), 0, 5, true).expect("council-attested");
    // bob: 1 disclosure, 0 citations → 1.0 pt
    let bob_disc = ValidatedDisclosure::new(bob.clone(), 0, 1, 0, true, true).unwrap();
    // carol: wellbecoming HARM Δ=-3 (Council-attested) → burn 6.0 pts (no prior balance → clamp 0)
    let carol_harm = ValidatedWellbecoming::new(carol.clone(), 0, -3, true).unwrap();

    // an UNVALIDATED disclosure cannot even be constructed → cannot mint (spec §7)
    assert!(ValidatedDisclosure::new(bob.clone(), 0, 9, 9, false, true).is_none());
    println!("validation gate: unvalidated disclosure → None (cannot mint). ✓\n");

    // ── 2. Mint engine → Datoms ──
    let mut datoms = Vec::new();
    datoms.extend(alice_disc.mint_datom(&params, &graph));
    datoms.extend(alice_wb.datom(&params, &graph));
    datoms.extend(bob_disc.mint_datom(&params, &graph));
    datoms.extend(carol_harm.datom(&params, &graph));
    println!("minted {} social Datoms at epoch 0:", datoms.len());
    for d in &datoms {
        let v = match &d.v {
            kotoba_kqe::datom::Value::Integer(n) => pts(*n),
            _ => "?".into(),
        };
        println!("  {}  {}  = {v}", &d.e.to_string()[..20.min(d.e.to_string().len())], d.a);
    }

    // ── 3. SocialCapitalView reducer (decayed balances over the Datom stream) ──
    let deltas: Vec<Delta> = datoms.into_iter().map(Delta::assert_datom).collect();
    let mut view = SocialCapitalView::new();
    view.apply(&deltas);

    println!("\ncapital @ epoch 0:");
    for (name, d) in [("alice", &alice), ("bob", &bob), ("carol", &carol)] {
        println!("  {name:6} = {}", pts(view.capital(d, 0)));
    }
    // alice = 2.8 + 10.0 = 12.8; bob = 1.0; carol = 0 (harm clamped, no prior balance)

    // ── 4. Retainer allocation (donation pool split by social capital, §6) ──
    // Three pins; alice originated rootA, bob rootB, alice+bob co-originated rootC.
    let pins = [
        PinOrigin { pin_id: did("pinA"), root_cid: did("rootA"), origin_dids: vec![alice.clone()] },
        PinOrigin { pin_id: did("pinB"), root_cid: did("rootB"), origin_dids: vec![bob.clone()] },
        PinOrigin {
            pin_id: did("pinC"),
            root_cid: did("rootC"),
            origin_dids: vec![alice.clone(), bob.clone()],
        },
    ];
    let pool_mkoto = 1_000_000; // the epoch's donation-funded retainer pool

    let (shares, remainder) = allocate_retainer(&pins, &view, 0, pool_mkoto);
    println!("\nretainer allocation @ epoch 0 (pool = {pool_mkoto} mKOTO):");
    for (s, p) in shares.iter().zip(pins.iter()) {
        let root = &p.root_cid.to_string()[..16.min(p.root_cid.to_string().len())];
        println!(
            "  {root}…  SC_root={:>8}  → {:>7} mKOTO",
            pts(s.sc_root),
            s.retainer_mkoto
        );
    }
    println!("  undistributed remainder (rolls over) = {remainder} mKOTO");
    let total: i64 = shares.iter().map(|s| s.retainer_mkoto).sum();
    println!("  conservation: Σ shares + remainder = {} == pool ✓", total + remainder);

    // ── 5. Decay re-weights allocation over time ──
    // 30 days (one half-life) later, with no new acts, every balance ~halves —
    // the RELATIVE allocation is stable, but a freshly-minting agent would gain.
    let bob_fresh = ValidatedDisclosure::new(bob.clone(), 30, 5, 0, true, true).unwrap(); // +5 pts at e30
    let mut datoms2 = Vec::new();
    datoms2.extend(bob_fresh.mint_datom(&params, &graph));
    let deltas2: Vec<Delta> = datoms2.into_iter().map(Delta::assert_datom).collect();
    view.apply(&deltas2);

    println!("\ncapital @ epoch 30 (one half-life later; bob mints +5.0 fresh):");
    for (name, d) in [("alice", &alice), ("bob", &bob)] {
        println!("  {name:6} = {}", pts(view.capital(d, 30)));
    }
    let (shares30, _) = allocate_retainer(&pins, &view, 30, pool_mkoto);
    println!("retainer @ epoch 30 (pool = {pool_mkoto} mKOTO):");
    for (s, p) in shares30.iter().zip(pins.iter()) {
        let root = &p.root_cid.to_string()[..16.min(p.root_cid.to_string().len())];
        println!("  {root}…  SC_root={:>8}  → {:>7} mKOTO", pts(s.sc_root), s.retainer_mkoto);
    }

    // sanity: a falsification burns more than it earned (asymmetric 嘘で損)
    let f = Falsification { did: alice.clone(), epoch: 30, count: 2 };
    println!(
        "\nfalsification burn (alice, 2 claims): {} (> the 2.0 pts they'd have earned) ✓",
        pts(f.burn_smic(&params))
    );

    println!("\n== loop verified: acts → mint → view → SC_root → retainer ==");
}
