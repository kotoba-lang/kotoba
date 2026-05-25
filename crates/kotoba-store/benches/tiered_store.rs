use criterion::{criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};
use kotoba_core::{cid::KotobaCid, store::BlockStore};
use kotoba_store::{BudgetedBlockStore, MemoryBlockStore, TieredBlockStore};

fn make_cid(n: u64) -> KotobaCid {
    KotobaCid::from_bytes(&n.to_le_bytes())
}

fn make_block(n: u64) -> Vec<u8> {
    format!("block-data-{n:020}").into_bytes()
}

fn bench_hot_put_get(c: &mut Criterion) {
    let mut group = c.benchmark_group("tiered/hot");

    for n in [1_000u64, 10_000] {
        group.throughput(Throughput::Elements(n));
        group.bench_with_input(BenchmarkId::new("put+get", n), &n, |b, &n| {
            b.iter(|| {
                let store = TieredBlockStore::new(MemoryBlockStore::new(), MemoryBlockStore::new());
                // Write directly through the TieredBlockStore (hot write + async cold)
                for i in 0..n {
                    let data = make_block(i);
                    let cid  = make_cid(i);
                    store.put(&cid, &data).unwrap();
                }
                for i in 0..n {
                    let cid = make_cid(i);
                    let _   = store.get(&cid).unwrap();
                }
            });
        });
    }
    group.finish();
}

fn bench_cold_promote(c: &mut Criterion) {
    let mut group = c.benchmark_group("tiered/cold_promote");

    for n in [100u64, 1_000] {
        group.throughput(Throughput::Elements(n));
        group.bench_with_input(BenchmarkId::from_parameter(n), &n, |b, &n| {
            b.iter(|| {
                let hot  = MemoryBlockStore::new();
                let cold = MemoryBlockStore::new();

                // Pre-populate cold directly (bypassing hot)
                for i in 0..n {
                    cold.put(&make_cid(i), &make_block(i)).unwrap();
                }

                let store = TieredBlockStore::new(hot, cold);
                // Read through — cold miss → promote to hot
                for i in 0..n {
                    let _ = store.get(&make_cid(i)).unwrap();
                }
                // Post-read, all should be in hot tier
                for i in 0..n {
                    assert!(store.has(&make_cid(i)));
                }
            });
        });
    }
    group.finish();
}

fn bench_budgeted_eviction(c: &mut Criterion) {
    c.bench_function("budgeted/evict_under_pressure", |b| {
        b.iter(|| {
            // 1 MB budget, inserting 2 MB worth of blocks
            let store = BudgetedBlockStore::new(MemoryBlockStore::new(), 1024 * 1024);
            for i in 0..256u64 {
                let data: Vec<u8> = vec![i as u8; 8192]; // 8 KB each → 2 MB total
                let cid = make_cid(i);
                let _  = store.put(&cid, &data);
            }
            store.used_bytes()
        });
    });
}

criterion_group!(
    benches,
    bench_hot_put_get,
    bench_cold_promote,
    bench_budgeted_eviction,
);
criterion_main!(benches);
