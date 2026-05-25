use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use kotoba_core::cid::KotobaCid;
use kotoba_kqe::{
    arrangement::Arrangement,
    quad::{Quad, QuadObject},
};

fn make_cid(n: u64) -> KotobaCid {
    KotobaCid::from_bytes(&n.to_le_bytes())
}

fn make_text_quad(s: u64, p: &str, o: &str) -> Quad {
    Quad {
        graph:     make_cid(0),
        subject:   make_cid(s),
        predicate: p.to_string(),
        object:    QuadObject::Text(o.to_string()),
    }
}

fn make_ref_quad(s: u64, p: &str, o: u64) -> Quad {
    Quad {
        graph:     make_cid(0),
        subject:   make_cid(s),
        predicate: p.to_string(),
        object:    QuadObject::Cid(make_cid(o)),
    }
}

fn bench_insert(c: &mut Criterion) {
    let mut group = c.benchmark_group("arrangement/insert");
    for n in [1_000u64, 10_000, 100_000] {
        group.throughput(Throughput::Elements(n));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            b.iter(|| {
                let mut arr = Arrangement::new();
                for i in 0..n {
                    arr.insert(&make_text_quad(i % 1000, "name", "value"));
                    arr.insert(&make_ref_quad(i % 1000, "knows", (i + 1) % 1000));
                }
                arr
            });
        });
    }
    group.finish();
}

fn bench_spo_lookup(c: &mut Criterion) {
    // Pre-build arrangement with 10k quads
    let mut arr = Arrangement::new();
    for i in 0..10_000u64 {
        arr.insert(&make_text_quad(i % 1000, "name", "Alice"));
    }
    let subject = make_cid(42);

    c.bench_function("arrangement/spo_lookup_eavt", |b| {
        b.iter(|| arr.get_objects(&subject, "name"));
    });
}

fn bench_pso_lookup(c: &mut Criterion) {
    let mut arr = Arrangement::new();
    for i in 0..10_000u64 {
        arr.insert(&make_text_quad(i % 1000, "role", "admin"));
    }

    c.bench_function("arrangement/pso_get_subjects_aevt", |b| {
        b.iter(|| arr.get_subjects_by_predicate("role"));
    });

    c.bench_function("arrangement/pso_get_by_predicate_aevt", |b| {
        b.iter(|| arr.get_by_predicate("role"));
    });
}

fn bench_pos_lookup(c: &mut Criterion) {
    let mut arr = Arrangement::new();
    for i in 0..10_000u64 {
        arr.insert(&make_text_quad(i, "status", if i % 2 == 0 { "active" } else { "inactive" }));
    }

    c.bench_function("arrangement/pos_lookup_avet", |b| {
        b.iter(|| arr.get_subjects_by_predicate_object("status", "active"));
    });
}

fn bench_ocp_lookup(c: &mut Criterion) {
    let mut arr = Arrangement::new();
    let target = make_cid(999);
    for i in 0..10_000u64 {
        arr.insert(&make_ref_quad(i % 1000, "knows", 999));
    }

    c.bench_function("arrangement/ocp_reverse_ref_vaet", |b| {
        b.iter(|| arr.get_referencing_subjects(&target));
    });
}

fn bench_predicate_prefix_scan(c: &mut Criterion) {
    let mut arr = Arrangement::new();
    for i in 0..10_000u64 {
        arr.insert(&make_text_quad(i % 100, &format!("weight/block/{}/attn/q", i % 32), "v"));
        arr.insert(&make_text_quad(i % 100, &format!("weight/block/{}/ffn/gate", i % 32), "v"));
    }
    let g = make_cid(0);

    c.bench_function("arrangement/prefix_scan_avet_weight", |b| {
        b.iter(|| arr.quads_with_predicate_prefix(&g, "weight/"));
    });
}

criterion_group!(
    benches,
    bench_insert,
    bench_spo_lookup,
    bench_pso_lookup,
    bench_pos_lookup,
    bench_ocp_lookup,
    bench_predicate_prefix_scan,
);
criterion_main!(benches);
