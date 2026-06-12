use crate::arrangement::Arrangement;
use crate::datalog::DatalogProgram;
use crate::delta::Delta;

/// MaterializedView — incrementally maintained Datalog query result
/// = Pregel Aggregator (cross-vertex Arrangement)
pub struct MaterializedView {
    pub name: String,
    pub program: DatalogProgram,
    pub state: Arrangement,
}

impl MaterializedView {
    pub fn new(name: impl Into<String>, program: DatalogProgram) -> Self {
        Self {
            name: name.into(),
            program,
            state: Arrangement::new(),
        }
    }

    /// Pregel Phase 2: apply incoming Deltas, produce out_deltas
    pub fn apply(&mut self, deltas: &[Delta]) -> Vec<Delta> {
        self.state.apply(deltas);
        self.program.evaluate_delta(deltas)
    }
}

/// `MvRegistry` — named, incrementally-maintained MaterializedViews.
///
/// The foundation for serving Datalog queries first-tier (ADR-2606041151 B):
/// register a program once, feed every commit's Δ through [`maintain`], and read
/// the accumulated derived facts from [`result`] instead of re-evaluating the
/// program from scratch on each request (which is what `kg.query` does today).
///
/// [`maintain`]: MvRegistry::maintain
/// [`result`]: MvRegistry::result
#[derive(Default)]
pub struct MvRegistry {
    views: std::collections::HashMap<String, MaterializedView>,
    /// Accumulated derived (IDB) facts per view, advanced by every `maintain`.
    results: std::collections::HashMap<String, Arrangement>,
}

impl MvRegistry {
    pub fn new() -> Self {
        Self::default()
    }

    /// Register (or replace) a view by name. Returns `true` when newly added,
    /// `false` when it replaced an existing view of the same name.
    pub fn register(&mut self, name: impl Into<String>, program: DatalogProgram) -> bool {
        let name = name.into();
        let is_new = !self.views.contains_key(&name);
        self.views
            .insert(name.clone(), MaterializedView::new(name.clone(), program));
        self.results.entry(name).or_default();
        is_new
    }

    pub fn contains(&self, name: &str) -> bool {
        self.views.contains_key(name)
    }

    pub fn names(&self) -> Vec<String> {
        self.views.keys().cloned().collect()
    }

    /// Incrementally maintain every registered view with a commit's deltas,
    /// accumulating each view's derived output into its result arrangement.
    /// Call once per committed transaction with that transaction's `Delta`s.
    pub fn maintain(&mut self, deltas: &[Delta]) {
        let names: Vec<String> = self.views.keys().cloned().collect();
        for name in names {
            let derived = self
                .views
                .get_mut(&name)
                .expect("view present")
                .apply(deltas);
            self.results.entry(name).or_default().apply(&derived);
        }
    }

    /// The accumulated derived facts of a registered view (the maintained query
    /// result), or `None` if the view is not registered.
    pub fn result(&self, name: &str) -> Option<&Arrangement> {
        self.results.get(name)
    }

    pub fn view(&self, name: &str) -> Option<&MaterializedView> {
        self.views.get(name)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::datalog::{Atom, BodyLiteral, DatalogRule, Term};
    use crate::datom::{Datom, Value};
    use crate::delta::Delta;
    use kotoba_core::cid::KotobaCid;

    fn cid(seed: &str) -> KotobaCid {
        KotobaCid::from_bytes(seed.as_bytes())
    }

    fn edge_datom(from: &str, to: &str) -> Datom {
        Datom::assert(cid(from), "edge".to_string(), Value::Cid(cid(to)), cid("g"))
    }

    fn edge_assert(from: &str, to: &str) -> Delta {
        Delta::assert_datom(edge_datom(from, to))
    }

    fn edge_retract(from: &str, to: &str) -> Delta {
        Delta::retract_datom(edge_datom(from, to))
    }

    fn make_rule(head_rel: &str, body_rel: &str) -> DatalogRule {
        DatalogRule {
            head: Atom {
                relation: head_rel.to_string(),
                args: vec![Term::Variable("X".into()), Term::Variable("Y".into())],
            },
            body: vec![BodyLiteral::Positive(Atom {
                relation: body_rel.to_string(),
                args: vec![Term::Variable("X".into()), Term::Variable("Y".into())],
            })],
        }
    }

    // ── Basic construction ─────────────────────────────────────────────────

    #[test]
    fn new_mv_has_empty_state() {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        let mv = MaterializedView::new("reachable", prog);
        assert!(mv.state.is_empty());
        assert_eq!(mv.name, "reachable");
    }

    // ── Apply: simple projection rule ─────────────────────────────────────

    #[test]
    fn apply_projects_edge_to_reachable() {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        let mut mv = MaterializedView::new("reachable", prog);

        let deltas = vec![edge_assert("a", "b"), edge_assert("b", "c")];
        let out = mv.apply(&deltas);

        // Output should contain derived reachable(a,b) and reachable(b,c)
        assert!(!out.is_empty(), "apply should produce derived deltas");
        let derived_rels: Vec<String> = out.iter().map(|d| d.attribute().to_string()).collect();
        assert!(
            derived_rels.iter().all(|r| r == "reachable"),
            "all derived quads should have relation 'reachable'"
        );

        let subjects: Vec<KotobaCid> = out.iter().map(|d| d.entity().clone()).collect();
        assert!(subjects.contains(&cid("a")));
        assert!(subjects.contains(&cid("b")));
    }

    // ── Apply: state accumulation across calls ────────────────────────────

    #[test]
    fn apply_accumulates_state_across_calls() {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        let mut mv = MaterializedView::new("reachable", prog);

        mv.apply(&[edge_assert("a", "b")]);
        assert_eq!(
            mv.state.len(),
            1,
            "state should have 1 quad after first apply"
        );

        mv.apply(&[edge_assert("b", "c")]);
        assert_eq!(
            mv.state.len(),
            2,
            "state should have 2 quads after second apply"
        );
    }

    // ── Apply: retraction removes from state ─────────────────────────────

    #[test]
    fn retract_removes_from_state() {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        let mut mv = MaterializedView::new("reachable", prog);

        mv.apply(&[edge_assert("a", "b")]);
        assert_eq!(mv.state.len(), 1);

        mv.apply(&[edge_retract("a", "b")]);
        assert_eq!(mv.state.len(), 0);
    }

    // ── End-to-end: SQL→Datalog→MV ───────────────────────────────────────

    #[test]
    fn sql_compiled_mv_derives_correct_quads() {
        use crate::sql::SqlMvCompiler;

        // SQL: SELECT a.s, a.o FROM edge AS a WHERE a.s = 'alice'
        // → reachable(X, Y) :- edge(X, Y), X = cid("alice")
        let compiled = SqlMvCompiler::compile(
            "SELECT a.s, a.o FROM edge AS a WHERE a.s = 'alice'",
            "reachable_from_alice",
        )
        .expect("SQL compile should succeed");

        let mut mv = MaterializedView::new("reachable_from_alice", compiled.program);

        // alice→bob and carol→dave — only alice→bob should be derived
        let out = mv.apply(&[edge_assert("alice", "bob"), edge_assert("carol", "dave")]);

        // Only alice→bob matches the WHERE clause
        let derived_subjects: Vec<KotobaCid> = out
            .iter()
            .filter(|d| d.attribute() == "reachable_from_alice")
            .map(|d| d.entity().clone())
            .collect();

        assert!(
            derived_subjects.contains(&cid("alice")),
            "alice should be derived"
        );
        assert!(
            !derived_subjects.contains(&cid("carol")),
            "carol should be filtered out"
        );
    }

    // ── Apply: empty delta slice ──────────────────────────────────────────

    #[test]
    fn apply_empty_deltas_returns_empty_and_leaves_state_unchanged() {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        let mut mv = MaterializedView::new("reachable", prog);

        let out = mv.apply(&[]);
        assert!(
            out.is_empty(),
            "empty delta input must produce no derived deltas"
        );
        assert!(
            mv.state.is_empty(),
            "state must remain empty after empty apply"
        );
    }

    // ── Apply: program with no rules ─────────────────────────────────────

    #[test]
    fn apply_with_no_rules_accumulates_state_but_derives_nothing() {
        let prog = DatalogProgram::new(); // no rules
        let mut mv = MaterializedView::new("noop", prog);

        let out = mv.apply(&[edge_assert("a", "b")]);
        assert!(out.is_empty(), "no rules → no derived deltas");
        assert_eq!(mv.state.len(), 1, "raw input delta still applied to state");
    }

    // ── Name round-trip ───────────────────────────────────────────────────

    #[test]
    fn name_preserved() {
        let mv = MaterializedView::new("my-view", DatalogProgram::new());
        assert_eq!(mv.name, "my-view");
    }

    // ── New tests ─────────────────────────────────────────────────────────────

    #[test]
    fn new_mv_state_is_empty_initially() {
        let mv = MaterializedView::new("empty", DatalogProgram::new());
        assert!(mv.state.is_empty());
        assert_eq!(mv.state.len(), 0);
    }

    #[test]
    fn apply_with_retract_on_empty_state_does_not_panic() {
        // Retracting a quad that was never asserted should be a no-op.
        let prog = DatalogProgram::new();
        let mut mv = MaterializedView::new("noop-retract", prog);
        // Should not panic or error.
        let out = mv.apply(&[edge_retract("x", "y")]);
        assert!(out.is_empty(), "no rules → no derived deltas");
        assert_eq!(
            mv.state.len(),
            0,
            "retract of phantom quad keeps state at 0"
        );
    }

    #[test]
    fn apply_multiple_asserts_accumulate_in_state() {
        let prog = DatalogProgram::new();
        let mut mv = MaterializedView::new("accumulate", prog);
        let quads: Vec<_> = (0u8..5)
            .map(|i| {
                let s = format!("s{i}");
                let t = format!("t{i}");
                edge_assert(&s, &t)
            })
            .collect();
        mv.apply(&quads);
        assert_eq!(mv.state.len(), 5, "five asserts → five quads in state");
    }

    #[test]
    fn assert_then_retract_same_quad_leaves_empty_state() {
        let prog = DatalogProgram::new();
        let mut mv = MaterializedView::new("assert-retract", prog);
        mv.apply(&[edge_assert("alice", "bob")]);
        assert_eq!(mv.state.len(), 1);
        mv.apply(&[edge_retract("alice", "bob")]);
        assert_eq!(mv.state.len(), 0);
    }

    #[test]
    fn apply_returns_empty_for_program_with_no_rules_any_input() {
        let prog = DatalogProgram::new(); // zero rules
        let mut mv = MaterializedView::new("zero-rules", prog);
        let deltas: Vec<_> = (0u8..3)
            .map(|i| edge_assert(&format!("a{i}"), &format!("b{i}")))
            .collect();
        let out = mv.apply(&deltas);
        assert!(out.is_empty(), "no rules → output always empty");
    }

    #[test]
    fn mv_name_is_accessible_from_field() {
        let name = "my-materialized-view";
        let mv = MaterializedView::new(name, DatalogProgram::new());
        assert_eq!(mv.name.as_str(), name);
    }

    #[test]
    fn state_len_increments_with_each_assert() {
        let prog = DatalogProgram::new();
        let mut mv = MaterializedView::new("inc", prog);
        for i in 0u8..10 {
            mv.apply(&[edge_assert(&format!("from{i}"), &format!("to{i}"))]);
            assert_eq!(mv.state.len(), (i as usize) + 1);
        }
    }

    // ── MvRegistry (ADR-2606041151 B) ─────────────────────────────────────

    fn reachable_prog() -> DatalogProgram {
        let mut prog = DatalogProgram::new();
        prog.add_rule(make_rule("reachable", "edge"));
        prog
    }

    #[test]
    fn registry_register_and_query() {
        let mut reg = MvRegistry::new();
        assert!(reg.register("reachable", reachable_prog()), "newly added");
        assert!(reg.contains("reachable"));
        assert_eq!(reg.names(), vec!["reachable".to_string()]);
        // re-register same name = replace → false
        assert!(!reg.register("reachable", reachable_prog()));
    }

    #[test]
    fn registry_maintains_incrementally_across_commits() {
        let mut reg = MvRegistry::new();
        reg.register("reachable", reachable_prog());

        // commit 1: two edges → two derived reachable facts
        reg.maintain(&[edge_assert("a", "b"), edge_assert("b", "c")]);
        assert_eq!(reg.result("reachable").unwrap().len(), 2);

        // commit 2: one more edge → accumulates, no full re-eval
        reg.maintain(&[edge_assert("c", "d")]);
        assert_eq!(
            reg.result("reachable").unwrap().len(),
            3,
            "derived facts accumulate across commits (incremental maintenance)"
        );
    }

    #[test]
    fn registry_unknown_view_is_none() {
        let reg = MvRegistry::new();
        assert!(reg.result("nope").is_none());
        assert!(reg.view("nope").is_none());
        assert!(!reg.contains("nope"));
    }
}
