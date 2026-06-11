//! Integration: deploy a real solc-compiled contract (Hello.sol) via apply_create
//! over the Datom-backed EVM — the same initcode `forge create` deploys (ADR-2606091500).

#[test]
fn deploys_real_solc_contract() {
    use kotoba_core::cid::KotobaCid;
    use kotoba_kqe::delta::Delta;
    use kotoba_kqe::evm_state::{account_datoms, EvmStateView};
    use kotoba_evm::{apply_create, RevmU256 as U256};
    let g = KotobaCid::from_bytes(b"g:evm");
    let mut from=[0u8;20]; from.copy_from_slice(&hex::decode("f39Fd6e51aad88F6F4ce6aB8827279cffFb92266").unwrap());
    let mut bal=[0u8;32]; bal[16..].copy_from_slice(&(10_000u128*1_000_000_000_000_000_000u128).to_be_bytes());
    let mut v=EvmStateView::new();
    v.apply(&account_datoms(&from,0,&bal,None,&g).into_iter().map(Delta::assert_datom).collect::<Vec<_>>());
    let init=hex::decode("6080604052602a60005534801561001557600080fd5b50610184806100256000396000f3fe608060405234801561001057600080fd5b50600436106100365760003560e01c80630c55699c1461003b57806360fe47b114610059575b600080fd5b610043610075565b60405161005091906100d5565b60405180910390f35b610073600480360381019061006e9190610121565b61007b565b005b60005481565b806000819055507fdf7a95aebff315db1b7716215d602ab537373cdb769232aae6055c06e798425b816040516100b191906100d5565b60405180910390a150565b6000819050919050565b6100cf816100bc565b82525050565b60006020820190506100ea60008301846100c6565b92915050565b600080fd5b6100fe816100bc565b811461010957600080fd5b50565b60008135905061011b816100f5565b92915050565b600060208284031215610137576101366100f0565b5b60006101458482850161010c565b9150509291505056fea2646970667358221220c7505a77636d7eb0788e3a1a086c6985cad6d8fdf23855225a8498af77412ea664736f6c63430008170033").unwrap();
    let out=apply_create(&v,from,U256::ZERO,init,0,30_000_000,&g).expect("exec");
    eprintln!("deploy success={} gas={} created={:?} output_len={}", out.success, out.gas_used, out.created.map(hex::encode), out.output.len());
    assert!(out.success, "deploy reverted");
}
