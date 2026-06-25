//! Code generation: typed AST → a real WebAssembly **core module** (MVP +
//! linear memory).
//!
//! Strategy is a deliberate two-pass emit so recursion and mutual recursion
//! work: pass 1 assigns every `defn` a stable type-index and function-index and
//! evaluates every `def` to a compile-time constant; pass 2 emits the bodies,
//! which may freely `call` any function (including themselves) by an index that
//! already exists.
//!
//! ## Value model
//!
//! Every value on the operand stack is an `i64`. Three interpretations:
//!   - **number / boolean**: the i64 is the value; booleans are `1`/`0`, truthy
//!     ⇔ non-zero.
//!   - **float**: the i64 holds the IEEE-754 **bit pattern** of an f64 (no
//!     runtime tag). Float-ness is inferred *statically* per expression
//!     (`is_float_expr`); arithmetic/comparison sites reinterpret the bits to
//!     f64 (`f64.reinterpret_i64`), run the `f64.*` op, and (for arithmetic)
//!     repack the result with `i64.reinterpret_f64`. Mixed int/float arithmetic
//!     promotes the int operand with `f64.convert_i64_s`.
//!   - **string handle**: a packed `(offset << 32) | (len & 0xFFFF_FFFF)` where
//!     `offset` is a byte offset into linear memory and `len` the byte length.
//!     `str-len` / `byte-at` operate on this handle.
//!
//! ## Memory substrate (Step 1/2 of the kotoba:kais roadmap)
//!
//! Every emitted module exports:
//!   - `memory`        — a single linear memory.
//!   - `cabi_realloc`  — the Canonical-ABI bump allocator the Component Model
//!     host calls to place lowered values into guest memory.
//!
//! String literals are laid out in an active data segment starting at
//! `DATA_BASE`; the bump heap starts immediately above them. This is the
//! linear-memory foundation that the future `list<u8>` Component export and
//! CBOR `InvokeContext` decode will build on (see `docs/ADR-clojure-wasm.md`).

use std::collections::{HashMap, HashSet};

use wasm_encoder::{
    BlockType, CodeSection, ConstExpr, DataSection, ElementSection, Elements, EntityType,
    ExportKind, ExportSection, Function, FunctionSection, GlobalSection, GlobalType, ImportSection,
    Instruction, MemArg, MemorySection, MemoryType, Module, RefType, TableSection, TableType,
    TypeSection, ValType,
};

use crate::ast::{Builtin, Expr, HostImport, Program};
use crate::CljError;

/// Byte offset where string/data literals begin. Low memory `[0, DATA_BASE)` is
/// left as a null/scratch guard region.
const DATA_BASE: u32 = 1024;
/// Bump-heap alignment for `cabi_realloc` returns and the heap base.
const HEAP_ALIGN: u32 = 16;
const WASM_PAGE: u32 = 65536;
/// Table index of the funcref table holding lambda-lifted closures (the only
/// table in the module, so index 0).
const CLOSURE_TABLE: u32 = 0;

/// Compile a parsed [`Program`] into WebAssembly bytes (core module; every
/// `defn` exported by name).
pub fn compile(program: &Program) -> Result<Vec<u8>, CljError> {
    compile_core_impl(program, &[], None)
}

/// Like [`compile`], but caps the emitted linear memory's **maximum** at
/// `max_pages` (64 KiB pages). The wasm engine then enforces the bound itself —
/// `memory.grow` past it fails — so a safe-clj module physically cannot exceed
/// its policy's `:memory-pages` budget, independent of any runtime
/// `StoreLimits`. Errors if the module's static data already needs more than
/// `max_pages`.
pub fn compile_with_memory_max(
    program: &Program,
    max_pages: Option<u32>,
) -> Result<Vec<u8>, CljError> {
    compile_core_impl(program, &[], max_pages)
}

/// The Canonical-ABI shape of the generated `run` entry wrapper's return value.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryAbi {
    /// `run: func(list<u8>) -> list<u8>` — 8-byte return area `[ptr, len]`.
    BytesToBytes,
    /// `run: func(list<u8>) -> result<list<u8>, string>` — always `ok`; 12-byte
    /// return area `[tag:u8 @0, ptr:i32 @4, len:i32 @8]` (the kotoba-node shape).
    BytesToResultBytes,
    /// `on-tick: func(epoch-ms: u64) -> result<list<u8>, string>` (M8). Input is
    /// a single `i64` value passed straight to the guest fn (no handle build);
    /// the return area is the same 12-byte `result<list<u8>,string>` shape.
    I64ToResultBytes,
    /// `on-kse: func(topic: string, payload: list<u8>) -> result<list<u8>, string>`
    /// (M9). Two (ptr,len) inputs → two guest handles; same 12-byte return area.
    StringBytesToResultBytes,
}

impl EntryAbi {
    /// The core wrapper function's wasm signature `(params) -> [i32 ret-area]`.
    fn wrapper_params(self) -> &'static [ValType] {
        match self {
            // (in_ptr, in_len)
            EntryAbi::BytesToBytes | EntryAbi::BytesToResultBytes => &[ValType::I32, ValType::I32],
            // (epoch: u64)
            EntryAbi::I64ToResultBytes => &[ValType::I64],
            // (topic_ptr, topic_len, payload_ptr, payload_len)
            EntryAbi::StringBytesToResultBytes => {
                &[ValType::I32, ValType::I32, ValType::I32, ValType::I32]
            }
        }
    }

    /// Number of params the wrapped guest `defn` must declare.
    fn guest_arity(self) -> usize {
        match self {
            EntryAbi::StringBytesToResultBytes => 2, // (topic, payload)
            // list<u8>/u64 inputs are a single guest value
            EntryAbi::BytesToBytes | EntryAbi::BytesToResultBytes | EntryAbi::I64ToResultBytes => 1,
        }
    }
}

/// A component entry point: the user `defn` to wrap, the ABI of its export, and
/// the WIT export name to bind it to. Multiple entries (e.g. `run` + `on-http`,
/// M7) can be emitted in one component, each wrapped under its own export name.
#[derive(Debug, Clone, Copy)]
pub struct Entry<'a> {
    pub name: &'a str,
    pub abi: EntryAbi,
    pub export_name: &'a str,
}

/// Compile a [`Program`] into a core module, optionally adding a Canonical-ABI
/// entry wrapper.
///
/// When `entry` is `Some`, the named arity-1 `defn` is wrapped by an exported
/// `run(in_ptr: i32, in_len: i32) -> ret_area: i32` function that realises the
/// Canonical ABI for the chosen [`EntryAbi`]: it packs the input `(ptr,len)`
/// into a string handle, calls the user function, then writes the returned
/// handle's `(ptr,len)` into a `cabi_realloc`'d return area and returns that
/// area's pointer. In this mode the user `defn`s are not exported by name (only
/// `run`, `memory`, `cabi_realloc` are), so the wrapper owns the `run` export
/// name unambiguously.
pub fn compile_core(program: &Program, entries: &[Entry]) -> Result<Vec<u8>, CljError> {
    compile_core_impl(program, entries, None)
}

/// Implementation of [`compile_core`] with an optional linear-memory page cap
/// (see [`compile_with_memory_max`]).
fn compile_core_impl(
    program: &Program,
    entries: &[Entry],
    max_pages: Option<u32>,
) -> Result<Vec<u8>, CljError> {
    // ---- Pass 0: collect string literals into one data blob ----------------
    let literals = collect_literals(program);

    // ---- Pass 1: constants + function signatures ---------------------------
    let consts = eval_consts(program, &literals)?;
    let float_defs = float_def_names(program);

    // ---- Host imports -------------------------------------------------------
    // Any used host-call builtin (e.g. `has-capability?`) becomes a wasm import.
    // Imports occupy function indices `0..num_imports`; every *defined* function
    // index is therefore offset by `import_base`. Getting this offset right is
    // the whole correctness story of import support.
    let host_imports = collect_host_imports(program);
    let import_base = host_imports.len() as u32;

    let mut types = TypeSection::new();
    let mut imports = ImportSection::new();
    let mut import_index: HashMap<HostImport, u32> = HashMap::new();
    for (i, imp) in host_imports.iter().enumerate() {
        let (params, results) = host_import_sig(*imp);
        let tidx = types.len();
        types.ty().function(params, results);
        let (module, field) = imp.module_field();
        imports.import(module, field, EntityType::Function(tidx));
        import_index.insert(*imp, i as u32);
    }

    let mut fn_index: HashMap<(String, usize), u32> = HashMap::new();
    for (i, f) in program.functions.iter().enumerate() {
        let arity = f.params.len();
        let key = (f.name.clone(), arity);
        if fn_index.contains_key(&key) {
            return Err(CljError::Codegen(format!(
                "function `{}` with arity {arity} defined twice",
                f.name
            )));
        }
        fn_index.insert(key, import_base + i as u32);
    }

    // Funcref table for lambda-lifted closures: slot `s` → the absolute function
    // index of the lifted fn carrying `table_slot == Some(s)`. Slots are dense
    // (0..K) and assigned in lifting order, so we just place each at its slot.
    let num_slots = program
        .functions
        .iter()
        .filter_map(|f| f.table_slot)
        .max()
        .map(|m| m + 1)
        .unwrap_or(0);
    let mut table_funcs: Vec<u32> = vec![0; num_slots as usize];
    for (i, f) in program.functions.iter().enumerate() {
        if let Some(slot) = f.table_slot {
            table_funcs[slot as usize] = import_base + i as u32;
        }
    }

    // Validate every entry point up front → (user fn index, abi, export name).
    let entry_targets: Vec<(u32, EntryAbi, &str)> = entries
        .iter()
        .map(|e| {
            let arity = e.abi.guest_arity();
            let idx = fn_index
                .get(&(e.name.to_string(), arity))
                .copied()
                .ok_or_else(|| {
                    CljError::Codegen(format!(
                        "component entry `(defn {} [{} args] …)` not found",
                        e.name, arity
                    ))
                })?;
            Ok((idx, e.abi, e.export_name))
        })
        .collect::<Result<_, CljError>>()?;

    // Distinct function types, keyed by arity (params: arity×i64 → i64).
    let mut type_for_arity: HashMap<usize, u32> = HashMap::new();
    let mut funcs = FunctionSection::new();
    let mut exports = ExportSection::new();
    for (i, f) in program.functions.iter().enumerate() {
        let arity = f.params.len();
        let type_idx = *type_for_arity.entry(arity).or_insert_with(|| {
            let idx = types.len();
            types
                .ty()
                .function(std::iter::repeat_n(ValType::I64, arity), [ValType::I64]);
            idx
        });
        funcs.function(type_idx);
        // In component mode the wrapper owns the export names; don't leak the
        // raw i64 functions (avoids a clash on the `run` name).
        if entry_targets.is_empty() {
            if let Some(export_name) = &f.export_name {
                exports.export(export_name, ExportKind::Func, import_base + i as u32);
            }
        }
    }

    // An indirect closure call of N args needs the function type for arity N+1
    // (the hidden `__self` pointer). A defined function of that arity may not
    // exist (e.g. `map`'s `(f x)` when no arity-2 `defn` is present), so ensure
    // every needed type is present and remember whether *any* indirect call
    // exists — a `call_indirect` is only valid if the module has a table.
    let indirect_arities = collect_call_value_arities(program);
    let has_indirect = !indirect_arities.is_empty();
    for a in &indirect_arities {
        let arity = a + 1;
        type_for_arity.entry(arity).or_insert_with(|| {
            let idx = types.len();
            types
                .ty()
                .function(std::iter::repeat_n(ValType::I64, arity), [ValType::I64]);
            idx
        });
    }

    // cabi_realloc: (old:i32, old_sz:i32, align:i32, new_sz:i32) -> i32
    let realloc_type = types.len();
    types.ty().function(
        [ValType::I32, ValType::I32, ValType::I32, ValType::I32],
        [ValType::I32],
    );
    let realloc_fn_index = import_base + program.functions.len() as u32;
    funcs.function(realloc_type);
    exports.export("cabi_realloc", ExportKind::Func, realloc_fn_index);

    // Canonical-ABI entry wrappers (component mode): one per entry, each under
    // its own WIT export name. The wrapper signature depends on the entry ABI
    // (e.g. `on-tick` takes one i64, others take (i32,i32)). All return one i32
    // (the return-area pointer).
    for (i, (user_idx, abi, export_name)) in entry_targets.iter().enumerate() {
        let wrapper_type = types.len();
        types
            .ty()
            .function(abi.wrapper_params().iter().copied(), [ValType::I32]);
        funcs.function(wrapper_type);
        let wrapper_index = realloc_fn_index + 1 + i as u32;
        exports.export(export_name, ExportKind::Func, wrapper_index);
        debug_assert!(*user_idx < realloc_fn_index);
    }

    // ---- Memory + heap global ----------------------------------------------
    let heap_start = align_up(DATA_BASE + literals.blob.len() as u32, HEAP_ALIGN);
    let min_pages = heap_start.div_ceil(WASM_PAGE).max(1) as u64;

    // Apply the policy memory cap, if any. The cell's static data already needs
    // `min_pages`, so a tighter cap is a hard error (the module cannot fit).
    let maximum = match max_pages {
        Some(mp) => {
            let mp = mp as u64;
            if mp < min_pages {
                return Err(CljError::Codegen(format!(
                    "module needs at least {min_pages} memory page(s) for its static \
                     data, but the policy `:memory-pages` allows only {mp}"
                )));
            }
            Some(mp)
        }
        None => None,
    };

    let mut memories = MemorySection::new();
    memories.memory(MemoryType {
        minimum: min_pages,
        maximum,
        memory64: false,
        shared: false,
        page_size_log2: None,
    });
    exports.export("memory", ExportKind::Memory, 0);

    // Global 0: the bump-heap pointer, mutable i32, initialised at heap_start.
    let mut globals = GlobalSection::new();
    globals.global(
        GlobalType {
            val_type: ValType::I32,
            mutable: true,
            shared: false,
        },
        &ConstExpr::i32_const(heap_start as i32),
    );
    const HEAP_GLOBAL: u32 = 0;

    // ---- Pass 2: bodies -----------------------------------------------------
    let mut code = CodeSection::new();
    for f in &program.functions {
        let mut cg = FnCtx {
            consts: &consts,
            fn_index: &fn_index,
            arity_type: &type_for_arity,
            import_index: &import_index,
            literals: &literals,
            scope: f
                .params
                .iter()
                .enumerate()
                .map(|(i, p)| (p.clone(), i as u32))
                .collect(),
            float_env: FloatEnv::new(float_defs.clone()),
            next_local: f.params.len() as u32,
            arity: f.params.len() as u32,
            realloc_index: realloc_fn_index,
            ctrl_depth: 0,
            loop_targets: Vec::new(),
            out: Vec::new(),
        };
        compile_body(&mut cg, &f.body)?;
        let extra_locals = cg.next_local - cg.arity;
        let mut func = Function::new([(extra_locals, ValType::I64)]);
        for ins in &cg.out {
            func.instruction(ins);
        }
        func.instruction(&Instruction::End);
        code.function(&func);
    }
    code.function(&cabi_realloc_fn(HEAP_GLOBAL));
    for (user_idx, abi, _export_name) in &entry_targets {
        code.function(&entry_wrapper_fn(*user_idx, realloc_fn_index, *abi));
    }

    // ---- Data segment -------------------------------------------------------
    let mut data = DataSection::new();
    if !literals.blob.is_empty() {
        data.active(
            0,
            &ConstExpr::i32_const(DATA_BASE as i32),
            literals.blob.iter().copied(),
        );
    }

    // Funcref table + element segment for closures. The table must exist whenever
    // the module contains *any* `call_indirect` (a CallValue) — even with zero
    // lifted closures — or the indirect call fails validation. The element
    // segment is only emitted when there are actual closures to install.
    let needs_table = has_indirect || !table_funcs.is_empty();
    let mut tables = TableSection::new();
    let mut elements = ElementSection::new();
    let elem_offset = ConstExpr::i32_const(0);
    if needs_table {
        tables.table(TableType {
            element_type: RefType::FUNCREF,
            table64: false,
            minimum: table_funcs.len() as u64,
            maximum: Some(table_funcs.len() as u64),
            shared: false,
        });
    }
    if !table_funcs.is_empty() {
        elements.active(
            Some(CLOSURE_TABLE),
            &elem_offset,
            Elements::Functions(table_funcs.as_slice().into()),
        );
    }

    // Sections must be emitted in ascending id order.
    let mut module = Module::new();
    module.section(&types); // 1
    if import_base > 0 {
        module.section(&imports); // 2
    }
    module.section(&funcs); // 3
    if needs_table {
        module.section(&tables); // 4
    }
    module.section(&memories); // 5
    module.section(&globals); // 6
    module.section(&exports); // 7
    if !table_funcs.is_empty() {
        module.section(&elements); // 9
    }
    module.section(&code); // 10
    module.section(&data); // 11
    Ok(module.finish())
}

fn align_up(x: u32, align: u32) -> u32 {
    (x + align - 1) & !(align - 1)
}

/// Interned string/byte literals and the concatenated data blob.
struct Literals {
    /// bytes → offset within `blob` (i.e. relative to DATA_BASE).
    offsets: HashMap<Vec<u8>, u32>,
    blob: Vec<u8>,
}

impl Literals {
    /// Packed string handle `(absolute-offset << 32) | len` for the literal.
    fn handle(&self, bytes: &[u8]) -> Option<i64> {
        let rel = *self.offsets.get(bytes)?;
        let abs = DATA_BASE + rel;
        Some(((abs as i64) << 32) | (bytes.len() as i64 & 0xFFFF_FFFF))
    }
}

/// The Canonical-ABI **core** signature a host import lowers to (params →
/// results), as the Component encoder computes it from the WIT function type.
///
/// `has-capability: func(string, string) -> bool`:
///   - each `string` flattens to `(ptr: i32, len: i32)` → 4 i32 params,
///   - `bool` flattens to a single `i32` result (≤ MAX_FLAT_RESULTS, so it is
///     returned directly — no indirect return area).
fn host_import_sig(imp: HostImport) -> (Vec<ValType>, Vec<ValType>) {
    match imp {
        HostImport::HasCapability => (
            vec![ValType::I32, ValType::I32, ValType::I32, ValType::I32],
            vec![ValType::I32],
        ),
        // `infer: func(string, list<u8>) -> result<list<u8>, string>`:
        //   - `string` and `list<u8>` each flatten to `(ptr,len)` → 4 i32 params,
        //   - the result flattens to >1 value, so it is returned **indirectly**:
        //     the caller appends a return-area pointer (5th i32 param) and the
        //     core import returns nothing. The host writes the 12-byte variant
        //     `[tag:u8 @0, ptr:i32 @4, len:i32 @8]` into that area.
        HostImport::LlmInfer => (
            vec![
                ValType::I32,
                ValType::I32,
                ValType::I32,
                ValType::I32,
                ValType::I32,
            ],
            vec![],
        ),
        // `assert-quad` / `retract-quad: func(q: quad) -> result<_, string>`:
        //   - the `quad` record flattens to its fields: 3 × `string` + 1 ×
        //     `list<u8>`, each a `(ptr,len)` pair → 8 i32 params,
        //   - `result<_, string>` flattens to >1 value (tag + err string) → the
        //     caller appends a return-area pointer (9th i32) and the core import
        //     returns nothing. Area: `[tag:u8 @0, err-ptr @4, err-len @8]`.
        HostImport::KqeAssertQuad | HostImport::KqeRetractQuad => (vec![ValType::I32; 9], vec![]),
        // `get-objects: func(string,string,string) -> list<list<u8>>`:
        //   - 3 strings → 6 i32 params,
        //   - a bare `list` result flattens to `(ptr,len)` = 2 values > 1 → an
        //     8-byte return area `[ptr @0, len @4]` (7th i32 param).
        HostImport::KqeGetObjects => (vec![ValType::I32; 7], vec![]),
        // `query: func(string) -> result<list<quad>, string>`:
        //   - 1 string → 2 i32 params,
        //   - indirect 12-byte return area `[tag:u8 @0, ptr @4, len @8]` (the
        //     same variant layout as `llm.infer`).
        HostImport::KqeQuery => (vec![ValType::I32; 3], vec![]),
    }
}

/// The distinct host imports a program uses — i.e. its capability surface.
///
/// This is the exact set [`crate::codegen::compile`] would emit into the wasm
/// import section, so [`crate::compile_safe_clj`] gates *this* set against the
/// policy: anything denied never reaches the module bytes.
pub fn used_host_imports(program: &Program) -> Vec<HostImport> {
    collect_host_imports(program)
}

/// Collect the distinct host imports the program uses, in first-seen order
/// (stable so emitted indices are deterministic).
fn collect_host_imports(program: &Program) -> Vec<HostImport> {
    let mut seen: Vec<HostImport> = Vec::new();
    let mut note = |imp: HostImport| {
        if !seen.contains(&imp) {
            seen.push(imp);
        }
    };
    fn walk(expr: &Expr, note: &mut impl FnMut(HostImport)) {
        match expr {
            Expr::Int(_) | Expr::Float(_) | Expr::Str(_) | Expr::Var(_) => {}
            Expr::If { cond, then, els } => {
                walk(cond, note);
                walk(then, note);
                walk(els, note);
            }
            Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
                bindings.iter().for_each(|(_, v)| walk(v, note));
                body.iter().for_each(|e| walk(e, note));
            }
            Expr::Recur(es) | Expr::Do(es) | Expr::Call { args: es, .. } => {
                es.iter().for_each(|e| walk(e, note));
            }
            Expr::Builtin { op, args } => {
                if let Some(imp) = op.host_import() {
                    note(imp);
                }
                args.iter().for_each(|e| walk(e, note));
            }
            Expr::Fn { body, .. } => body.iter().for_each(|e| walk(e, note)),
            Expr::MakeClosure { captures, .. } => captures.iter().for_each(|e| walk(e, note)),
            Expr::ClosureRef(_) => {}
            Expr::CallValue { f, args } => {
                walk(f, note);
                args.iter().for_each(|e| walk(e, note));
            }
        }
    }
    for d in &program.defs {
        walk(&d.value, &mut note);
    }
    for f in &program.functions {
        for e in &f.body {
            walk(e, &mut note);
        }
    }
    seen
}

/// Every distinct `args.len()` appearing in a `CallValue` (indirect closure
/// call) anywhere in the program. Used to (a) pre-create the needed
/// `call_indirect` function types and (b) decide whether a funcref table is
/// required at all.
fn collect_call_value_arities(program: &Program) -> std::collections::HashSet<usize> {
    let mut out = std::collections::HashSet::new();
    fn walk(e: &Expr, out: &mut std::collections::HashSet<usize>) {
        match e {
            Expr::Int(_) | Expr::Float(_) | Expr::Str(_) | Expr::Var(_) | Expr::ClosureRef(_) => {}
            Expr::If { cond, then, els } => {
                walk(cond, out);
                walk(then, out);
                walk(els, out);
            }
            Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
                bindings.iter().for_each(|(_, v)| walk(v, out));
                body.iter().for_each(|e| walk(e, out));
            }
            Expr::Do(es) | Expr::Recur(es) | Expr::Call { args: es, .. } => {
                es.iter().for_each(|e| walk(e, out));
            }
            Expr::Builtin { args, .. } => args.iter().for_each(|e| walk(e, out)),
            Expr::Fn { body, .. } => body.iter().for_each(|e| walk(e, out)),
            Expr::MakeClosure { captures, .. } => captures.iter().for_each(|e| walk(e, out)),
            Expr::CallValue { f, args } => {
                out.insert(args.len());
                walk(f, out);
                args.iter().for_each(|e| walk(e, out));
            }
        }
    }
    for d in &program.defs {
        walk(&d.value, &mut out);
    }
    for f in &program.functions {
        f.body.iter().for_each(|e| walk(e, &mut out));
    }
    out
}

fn collect_literals(program: &Program) -> Literals {
    let mut offsets: HashMap<Vec<u8>, u32> = HashMap::new();
    let mut blob: Vec<u8> = Vec::new();
    let mut intern = |bytes: &[u8]| {
        if !offsets.contains_key(bytes) {
            offsets.insert(bytes.to_vec(), blob.len() as u32);
            blob.extend_from_slice(bytes);
        }
    };
    for d in &program.defs {
        walk_strings(&d.value, &mut intern);
    }
    for f in &program.functions {
        for e in &f.body {
            walk_strings(e, &mut intern);
        }
    }
    Literals { offsets, blob }
}

fn walk_strings(expr: &Expr, f: &mut impl FnMut(&[u8])) {
    match expr {
        Expr::Str(b) => f(b),
        Expr::Int(_) | Expr::Float(_) | Expr::Var(_) => {}
        Expr::If { cond, then, els } => {
            walk_strings(cond, f);
            walk_strings(then, f);
            walk_strings(els, f);
        }
        Expr::Let { bindings, body } | Expr::Loop { bindings, body } => {
            for (_, v) in bindings {
                walk_strings(v, f);
            }
            body.iter().for_each(|e| walk_strings(e, f));
        }
        Expr::Recur(es)
        | Expr::Do(es)
        | Expr::Builtin { args: es, .. }
        | Expr::Call { args: es, .. } => {
            es.iter().for_each(|e| walk_strings(e, f));
        }
        Expr::Fn { body, .. } => body.iter().for_each(|e| walk_strings(e, f)),
        Expr::MakeClosure { captures, .. } => captures.iter().for_each(|e| walk_strings(e, f)),
        Expr::ClosureRef(_) => {}
        Expr::CallValue { f: callee, args } => {
            walk_strings(callee, f);
            args.iter().for_each(|e| walk_strings(e, f));
        }
    }
}

/// The Canonical-ABI bump allocator. No free; `realloc` of an existing block
/// just allocates fresh (sufficient for lowering values into guest memory).
fn cabi_realloc_fn(heap_global: u32) -> Function {
    // params: 0=old_ptr 1=old_sz 2=align 3=new_sz ; locals: 4=aligned 5=new_heap
    let mut f = Function::new([(2, ValType::I32)]);

    // aligned = (heap + align - 1) & ~(align - 1)
    f.instruction(&Instruction::GlobalGet(heap_global));
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I32Add);
    f.instruction(&Instruction::I32Const(1));
    f.instruction(&Instruction::I32Sub);
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I32Const(1));
    f.instruction(&Instruction::I32Sub);
    f.instruction(&Instruction::I32Const(-1));
    f.instruction(&Instruction::I32Xor); // ~(align-1)
    f.instruction(&Instruction::I32And);
    f.instruction(&Instruction::LocalSet(4)); // aligned

    // new_heap = aligned + new_sz
    f.instruction(&Instruction::LocalGet(4));
    f.instruction(&Instruction::LocalGet(3));
    f.instruction(&Instruction::I32Add);
    f.instruction(&Instruction::LocalSet(5)); // new_heap

    // if new_heap > memory.size * 65536: grow by ceil(deficit / 65536) pages
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::MemorySize(0));
    f.instruction(&Instruction::I32Const(16));
    f.instruction(&Instruction::I32Shl);
    f.instruction(&Instruction::I32GtU);
    f.instruction(&Instruction::If(BlockType::Empty));
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::MemorySize(0));
    f.instruction(&Instruction::I32Const(16));
    f.instruction(&Instruction::I32Shl);
    f.instruction(&Instruction::I32Sub); // deficit bytes
    f.instruction(&Instruction::I32Const((WASM_PAGE - 1) as i32));
    f.instruction(&Instruction::I32Add);
    f.instruction(&Instruction::I32Const(16));
    f.instruction(&Instruction::I32ShrU); // pages
    f.instruction(&Instruction::MemoryGrow(0));
    f.instruction(&Instruction::Drop);
    f.instruction(&Instruction::End);

    // heap = new_heap ; return aligned
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::GlobalSet(heap_global));
    f.instruction(&Instruction::LocalGet(4));
    f.instruction(&Instruction::End);
    f
}

/// The Canonical-ABI `run` wrapper.
///
/// Core signature `(in_ptr: i32, in_len: i32) -> ret_area: i32`:
///   1. pack the input `(ptr,len)` into a string handle `(ptr<<32)|len`,
///   2. call the user entry function (handle → handle),
///   3. allocate the return area via `cabi_realloc` and populate it per `abi`,
///   4. return the area pointer (the Canonical-ABI return-area convention).
///
/// - [`EntryAbi::BytesToBytes`]: 8-byte area `[out_ptr @0, out_len @4]`.
/// - [`EntryAbi::BytesToResultBytes`]: 12-byte area for `result<list<u8>,string>`
///   in the `ok` case — `[tag:u8=0 @0, out_ptr:i32 @4, out_len:i32 @8]`.
fn entry_wrapper_fn(user_fn_index: u32, realloc_index: u32, abi: EntryAbi) -> Function {
    // `on-tick` has a distinct (i64)->i32 shape: pass the epoch value straight
    // to the guest fn (no input-handle build), then pack result<list<u8>,string>.
    if matches!(abi, EntryAbi::I64ToResultBytes) {
        return tick_wrapper_fn(user_fn_index, realloc_index);
    }
    if matches!(abi, EntryAbi::StringBytesToResultBytes) {
        return kse_wrapper_fn(user_fn_index, realloc_index);
    }
    // params: 0=in_ptr 1=in_len ; locals: 2=ret_handle(i64) 3=area(i32)
    let mut f = Function::new([(1, ValType::I64), (1, ValType::I32)]);
    let store32 = |offset: u64| MemArg {
        offset,
        align: 2,
        memory_index: 0,
    };
    let store8 = |offset: u64| MemArg {
        offset,
        align: 0,
        memory_index: 0,
    };
    // (ptr_off, len_off, area_size) for each ABI; result<> reserves a tag byte.
    let (ptr_off, len_off, area_size) = match abi {
        EntryAbi::BytesToBytes => (0u64, 4u64, 8i32),
        EntryAbi::BytesToResultBytes => (4u64, 8u64, 12i32),
        // handled by early-returns to dedicated wrappers above
        EntryAbi::I64ToResultBytes => unreachable!("I64 ABI uses tick_wrapper_fn"),
        EntryAbi::StringBytesToResultBytes => {
            unreachable!("string+bytes ABI uses kse_wrapper_fn")
        }
    };

    // handle = (in_ptr as u64 << 32) | (in_len as u64)
    f.instruction(&Instruction::LocalGet(0));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64Shl);
    f.instruction(&Instruction::LocalGet(1));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Or);
    // ret_handle = user_fn(handle)
    f.instruction(&Instruction::Call(user_fn_index));
    f.instruction(&Instruction::LocalSet(2));

    // area = cabi_realloc(0, 0, align=4, new_sz=area_size)
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(4));
    f.instruction(&Instruction::I32Const(area_size));
    f.instruction(&Instruction::Call(realloc_index));
    f.instruction(&Instruction::LocalSet(3));

    // result<> ok-discriminant: area[0] = 0u8
    if matches!(abi, EntryAbi::BytesToResultBytes) {
        f.instruction(&Instruction::LocalGet(3));
        f.instruction(&Instruction::I32Const(0));
        f.instruction(&Instruction::I32Store8(store8(0)));
    }

    // area[ptr_off] = out_ptr = ret_handle >>> 32
    f.instruction(&Instruction::LocalGet(3));
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64ShrU);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(ptr_off)));

    // area[len_off] = out_len = ret_handle & 0xFFFF_FFFF
    f.instruction(&Instruction::LocalGet(3));
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I64Const(0xFFFF_FFFF));
    f.instruction(&Instruction::I64And);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(len_off)));

    // return area
    f.instruction(&Instruction::LocalGet(3));
    f.instruction(&Instruction::End);
    f
}

/// `on-tick` wrapper (M8): `(epoch:i64) -> i32` returning a 12-byte
/// `result<list<u8>,string>` area `[tag:u8=0 @0, out_ptr @4, out_len @8]`.
/// The epoch value is passed straight to the guest fn (no input-handle build).
fn tick_wrapper_fn(user_fn_index: u32, realloc_index: u32) -> Function {
    // param 0 = epoch(i64) ; locals: 1=ret_handle(i64) 2=area(i32)
    let mut f = Function::new([(1, ValType::I64), (1, ValType::I32)]);
    let store32 = |offset: u64| MemArg {
        offset,
        align: 2,
        memory_index: 0,
    };
    let store8 = |offset: u64| MemArg {
        offset,
        align: 0,
        memory_index: 0,
    };

    // ret_handle = user_fn(epoch)   — epoch is the guest fn's i64 value arg
    f.instruction(&Instruction::LocalGet(0));
    f.instruction(&Instruction::Call(user_fn_index));
    f.instruction(&Instruction::LocalSet(1));

    // area = cabi_realloc(0, 0, align=4, new_sz=12)
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(4));
    f.instruction(&Instruction::I32Const(12));
    f.instruction(&Instruction::Call(realloc_index));
    f.instruction(&Instruction::LocalSet(2));

    // area[0] = ok discriminant (0)
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Store8(store8(0)));

    // area[4] = out_ptr = ret_handle >>> 32
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::LocalGet(1));
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64ShrU);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(4)));

    // area[8] = out_len = ret_handle & 0xFFFF_FFFF
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::LocalGet(1));
    f.instruction(&Instruction::I64Const(0xFFFF_FFFF));
    f.instruction(&Instruction::I64And);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(8)));

    // return area
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::End);
    f
}

/// `on-kse` wrapper (M9): `(topic_ptr, topic_len, payload_ptr, payload_len) -> i32`.
/// Builds two guest handles `(ptr<<32)|len` (topic, payload), calls the arity-2
/// guest fn, and packs `result<list<u8>,string>` (ok) into a 12-byte area.
fn kse_wrapper_fn(user_fn_index: u32, realloc_index: u32) -> Function {
    // params: 0=topic_ptr 1=topic_len 2=payload_ptr 3=payload_len
    // locals:  4=ret_handle(i64) 5=area(i32)
    let mut f = Function::new([(1, ValType::I64), (1, ValType::I32)]);
    let store32 = |offset: u64| MemArg {
        offset,
        align: 2,
        memory_index: 0,
    };
    let store8 = |offset: u64| MemArg {
        offset,
        align: 0,
        memory_index: 0,
    };

    // topic handle = (topic_ptr << 32) | topic_len
    f.instruction(&Instruction::LocalGet(0));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64Shl);
    f.instruction(&Instruction::LocalGet(1));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Or);
    // payload handle = (payload_ptr << 32) | payload_len
    f.instruction(&Instruction::LocalGet(2));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64Shl);
    f.instruction(&Instruction::LocalGet(3));
    f.instruction(&Instruction::I64ExtendI32U);
    f.instruction(&Instruction::I64Or);
    // ret_handle = on-kse(topic, payload)   (args consumed in push order)
    f.instruction(&Instruction::Call(user_fn_index));
    f.instruction(&Instruction::LocalSet(4));

    // area = cabi_realloc(0, 0, align=4, new_sz=12)
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Const(4));
    f.instruction(&Instruction::I32Const(12));
    f.instruction(&Instruction::Call(realloc_index));
    f.instruction(&Instruction::LocalSet(5));

    // area[0] = ok discriminant (0)
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::I32Const(0));
    f.instruction(&Instruction::I32Store8(store8(0)));

    // area[4] = out_ptr = ret_handle >>> 32
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::LocalGet(4));
    f.instruction(&Instruction::I64Const(32));
    f.instruction(&Instruction::I64ShrU);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(4)));

    // area[8] = out_len = ret_handle & 0xFFFF_FFFF
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::LocalGet(4));
    f.instruction(&Instruction::I64Const(0xFFFF_FFFF));
    f.instruction(&Instruction::I64And);
    f.instruction(&Instruction::I32WrapI64);
    f.instruction(&Instruction::I32Store(store32(8)));

    // return area
    f.instruction(&Instruction::LocalGet(5));
    f.instruction(&Instruction::End);
    f
}

/// A live `loop` target: the local slots holding its bindings, and the wasm
/// control depth at the point just inside its `loop` block. A `recur` rebinds
/// these locals and `br`s by `current_depth - frame_depth`.
struct LoopTarget {
    locals: Vec<u32>,
    frame_depth: u32,
}

/// Tracks which symbols (`def` globals and `let`-bound locals) carry a float
/// value (IEEE-754 bit pattern in the i64 slot). Used by [`is_float_expr`] to
/// decide whether a variable reference resolves to a float.
///
/// `defs` is computed once from the program's top-level `def` forms and
/// shared across all function bodies. `locals` is a scope-stack of
/// `(name, is_float)` pairs with the same push/pop discipline as
/// `FnCtx::scope`.
struct FloatEnv {
    /// Names of top-level `def` constants whose initialiser is a float.
    defs: HashSet<String>,
    /// `(name, is_float)` pairs for `let`/`loop` bindings in scope.
    /// Latest binding for a given name shadows earlier ones (same as `scope`).
    locals: Vec<(String, bool)>,
}

impl FloatEnv {
    fn new(defs: HashSet<String>) -> Self {
        Self {
            defs,
            locals: Vec::new(),
        }
    }
    /// Push a `let`/`loop` binding. `is_float` should be the result of
    /// `is_float_expr` evaluated on the binding's init expression.
    fn push(&mut self, name: String, is_float: bool) {
        self.locals.push((name, is_float));
    }
    /// Pop `n` bindings (restore scope to a saved depth).
    fn truncate(&mut self, saved: usize) {
        self.locals.truncate(saved);
    }
    /// Look up whether `name` is a float — checks locals (innermost first),
    /// then defs; unknown symbols return `false` (conservative).
    fn is_float(&self, name: &str) -> bool {
        // locals: scan in reverse so the innermost binding wins.
        if let Some((_, f)) = self.locals.iter().rev().find(|(n, _)| n == name) {
            return *f;
        }
        self.defs.contains(name)
    }
}

/// Per-function compilation context.
struct FnCtx<'a> {
    consts: &'a HashMap<String, i64>,
    fn_index: &'a HashMap<(String, usize), u32>,
    /// wasm function-type index for a user-fn of a given arity (params×i64 → i64).
    /// `call_indirect` of a closure with N args needs the type for arity `N+1`
    /// (the hidden `__self` closure pointer is the extra leading parameter).
    arity_type: &'a HashMap<usize, u32>,
    /// Host-import → wasm function index (imports occupy `0..num_imports`).
    import_index: &'a HashMap<HostImport, u32>,
    literals: &'a Literals,
    /// (name, local-index) pairs; latest binding shadows earlier ones.
    scope: Vec<(String, u32)>,
    /// Float-type environment: tracks which `def` globals and `let`/`loop`
    /// locals carry a float value (so `is_float_expr` can infer float-ness of
    /// variable references).
    float_env: FloatEnv,
    next_local: u32,
    arity: u32,
    /// Function index of the module's `cabi_realloc`, so `bytes-alloc` can call
    /// it to obtain heap space for a byte buffer.
    realloc_index: u32,
    /// Count of currently-open wasm control frames (`if`/`loop`). Used to turn
    /// an enclosing loop's recorded depth into a relative `br` label index.
    ctrl_depth: u32,
    /// Stack of enclosing `loop` targets (innermost last).
    loop_targets: Vec<LoopTarget>,
    out: Vec<Instruction<'a>>,
}

impl<'a> FnCtx<'a> {
    fn emit(&mut self, ins: Instruction<'a>) {
        self.out.push(ins);
    }
    fn resolve(&self, name: &str) -> Option<u32> {
        self.scope
            .iter()
            .rev()
            .find(|(n, _)| n == name)
            .map(|(_, i)| *i)
    }
    fn alloc_local(&mut self) -> u32 {
        let i = self.next_local;
        self.next_local += 1;
        i
    }
    /// Emit a control-frame opener (`if`/`loop`) and account for its depth.
    fn open_frame(&mut self, ins: Instruction<'a>) {
        self.emit(ins);
        self.ctrl_depth += 1;
    }
    /// Emit the matching `end` and pop the control-frame depth.
    fn close_frame(&mut self) {
        self.emit(Instruction::End);
        self.ctrl_depth -= 1;
    }
}

/// Compile a body (implicit `do`): all-but-last are dropped, last is the value.
fn compile_body(cg: &mut FnCtx, body: &[Expr]) -> Result<(), CljError> {
    let (last, init) = body
        .split_last()
        .ok_or_else(|| CljError::Codegen("empty function/let body".into()))?;
    for e in init {
        compile_expr(cg, e)?;
        cg.emit(Instruction::Drop);
    }
    compile_expr(cg, last)
}

/// `(loop [b v …] body…)` — sequential-init bindings (like `let`) that double as
/// a `recur` target. Lowers to a wasm `loop (result i64)`: the body either
/// leaves an `i64` (the exit value, taken as the loop's result) or `recur`s
/// (rebind the binding locals, then `br` back to the top).
fn compile_loop(
    cg: &mut FnCtx,
    bindings: &[(String, Expr)],
    body: &[Expr],
) -> Result<(), CljError> {
    let saved_scope = cg.scope.len();
    let saved_float = cg.float_env.locals.len();
    // Sequential init: each binding sees the previous ones (identical to `let`).
    let mut locals = Vec::with_capacity(bindings.len());
    for (name, val) in bindings {
        let is_float = is_float_expr(val, &cg.float_env);
        compile_expr(cg, val)?;
        let idx = cg.alloc_local();
        cg.emit(Instruction::LocalSet(idx));
        cg.scope.push((name.clone(), idx));
        cg.float_env.push(name.clone(), is_float);
        locals.push(idx);
    }

    cg.open_frame(Instruction::Loop(BlockType::Result(ValType::I64)));
    cg.loop_targets.push(LoopTarget {
        locals,
        frame_depth: cg.ctrl_depth, // depth as seen from just inside the loop
    });
    compile_body(cg, body)?;
    cg.loop_targets.pop();
    cg.close_frame();

    cg.scope.truncate(saved_scope); // loop bindings leave scope; slots stay
    cg.float_env.truncate(saved_float);
    Ok(())
}

/// `(recur args…)` — rebind the innermost enclosing `loop` and jump to its top.
/// All args are evaluated first (reading the *old* bindings), then written back,
/// so the rebind is parallel. The trailing `br` makes the code after it
/// unreachable, which polymorphically satisfies the surrounding `i64` slot.
fn compile_recur(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    let (frame_depth, locals) = match cg.loop_targets.last() {
        Some(t) => (t.frame_depth, t.locals.clone()),
        None => return Err(CljError::Codegen("`recur` used outside of a `loop`".into())),
    };
    if args.len() != locals.len() {
        return Err(CljError::Codegen(format!(
            "`recur` expects {} value(s) to match the loop bindings, got {}",
            locals.len(),
            args.len()
        )));
    }
    // Evaluate every new value first (they read the current binding locals).
    for a in args {
        compile_expr(cg, a)?;
    }
    // Pop into the binding locals in reverse (stack top is the last arg).
    for &idx in locals.iter().rev() {
        cg.emit(Instruction::LocalSet(idx));
    }
    // Relative label: how many frames between here and the loop header.
    let label = cg.ctrl_depth - frame_depth;
    cg.emit(Instruction::Br(label));
    Ok(())
}

/// Compile an expression, leaving exactly one `i64` on the stack.
fn compile_expr(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    match expr {
        Expr::Int(i) => cg.emit(Instruction::I64Const(*i)),

        // A float literal is stored in the uniform i64 slot as its IEEE-754 bit
        // pattern (no runtime tag). Float-arithmetic sites reinterpret it back
        // to f64 via `f64.reinterpret_i64` (see `compile_expr_as_f64`).
        Expr::Float(f) => cg.emit(Instruction::I64Const(f.to_bits() as i64)),

        Expr::Str(bytes) => {
            let handle = cg
                .literals
                .handle(bytes)
                .ok_or_else(|| CljError::Codegen("string literal not interned".into()))?;
            cg.emit(Instruction::I64Const(handle));
        }

        Expr::Var(name) => {
            if let Some(idx) = cg.resolve(name) {
                cg.emit(Instruction::LocalGet(idx));
            } else if let Some(c) = cg.consts.get(name) {
                cg.emit(Instruction::I64Const(*c));
            } else {
                return Err(CljError::Codegen(format!("unbound symbol `{name}`")));
            }
        }

        Expr::If { cond, then, els } => {
            compile_truthy_i32(cg, cond)?;
            cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
            compile_expr(cg, then)?;
            cg.emit(Instruction::Else);
            compile_expr(cg, els)?;
            cg.close_frame();
        }

        Expr::Let { bindings, body } => {
            let saved_scope = cg.scope.len();
            let saved_float = cg.float_env.locals.len();
            for (name, val) in bindings {
                let is_float = is_float_expr(val, &cg.float_env);
                compile_expr(cg, val)?;
                let idx = cg.alloc_local();
                cg.emit(Instruction::LocalSet(idx));
                cg.scope.push((name.clone(), idx));
                cg.float_env.push(name.clone(), is_float);
            }
            compile_body(cg, body)?;
            cg.scope.truncate(saved_scope); // bindings leave scope; local slots stay allocated
            cg.float_env.truncate(saved_float);
        }

        Expr::Loop { bindings, body } => compile_loop(cg, bindings, body)?,

        Expr::Recur(args) => compile_recur(cg, args)?,

        Expr::Do(exprs) => compile_body(cg, exprs)?,

        Expr::Builtin { op, args } => compile_builtin(cg, *op, args)?,

        Expr::Call { name, args } => {
            let arity = args.len();
            let idx = cg
                .fn_index
                .get(&(name.clone(), arity))
                .copied()
                .ok_or_else(|| {
                    CljError::Codegen(format!(
                        "call to unknown function `{name}` with arity {arity}"
                    ))
                })?;
            for a in args {
                compile_expr(cg, a)?;
            }
            cg.emit(Instruction::Call(idx));
        }

        // `(fn …)` must have been rewritten by lambda-lifting (lift_program).
        Expr::Fn { .. } => {
            return Err(CljError::Codegen(
                "internal error: `(fn …)` reached codegen un-lifted".into(),
            ))
        }

        // Read capture slot `n` from the current closure record. Local 0 is the
        // `__self` pointer (an i64 handle); the record is `[slot@0, cap0@8, …]`.
        Expr::ClosureRef(slot) => {
            cg.emit(Instruction::LocalGet(0));
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I64Load(mem64(8 + 8 * (*slot as u64))));
        }

        // Allocate `[table-slot, captures…]` and yield the record pointer (i64).
        Expr::MakeClosure {
            table_slot,
            captures,
        } => {
            let size = 8 + 8 * captures.len() as i32;
            let rec = cg.alloc_local();
            // rec = cabi_realloc(0, 0, HEAP_ALIGN, size)
            cg.emit(Instruction::I32Const(0));
            cg.emit(Instruction::I32Const(0));
            cg.emit(Instruction::I32Const(HEAP_ALIGN as i32));
            cg.emit(Instruction::I32Const(size));
            let realloc = cg.realloc_index;
            cg.emit(Instruction::Call(realloc));
            cg.emit(Instruction::I64ExtendI32U);
            cg.emit(Instruction::LocalSet(rec));
            // record[0] = table_slot
            cg.emit(Instruction::LocalGet(rec));
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I64Const(*table_slot as i64));
            cg.emit(Instruction::I64Store(mem64(0)));
            // record[8 + 8*i] = captures[i]
            for (i, cap) in captures.iter().enumerate() {
                cg.emit(Instruction::LocalGet(rec));
                cg.emit(Instruction::I32WrapI64);
                compile_expr(cg, cap)?;
                cg.emit(Instruction::I64Store(mem64(8 + 8 * i as u64)));
            }
            cg.emit(Instruction::LocalGet(rec));
        }

        // Indirect call: push `__self` (the closure ptr) + args, then the table
        // slot read from the record, and `call_indirect` the funcref table.
        Expr::CallValue { f, args } => {
            let type_idx = *cg.arity_type.get(&(args.len() + 1)).ok_or_else(|| {
                CljError::Codegen(format!(
                    "no closure of arity {} exists to call indirectly \
                     (define a matching `(fn …)`)",
                    args.len()
                ))
            })?;
            let clo = cg.alloc_local();
            compile_expr(cg, f)?;
            cg.emit(Instruction::LocalSet(clo));
            // __self
            cg.emit(Instruction::LocalGet(clo));
            // args
            for a in args {
                compile_expr(cg, a)?;
            }
            // table slot = record[0]
            cg.emit(Instruction::LocalGet(clo));
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I64Load(mem64(0)));
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::CallIndirect {
                type_index: type_idx,
                table_index: CLOSURE_TABLE,
            });
        }
    }
    Ok(())
}

/// Compile `expr` and convert the resulting i64 to an i32 truthiness flag
/// (1 if non-zero, 0 if zero) suitable as a wasm `if`/`br_if` condition.
fn compile_truthy_i32(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    // Peephole: a binary comparison already yields an i32 0/1 — exactly what a
    // wasm `if` wants. Emit `a; b; <cmp>` and stop, skipping the default
    // `extend_i32_u; const 0; i64.ne` round-trip (3 dead ops per branch in the
    // i64-everything model). Semantically identical: `(x cmp y) != 0` ⇔ `x cmp y`.
    if let Expr::Builtin { op, args } = expr {
        if args.len() == 2 {
            if let Some(cmp) = comparison_i32_instruction(*op) {
                compile_expr(cg, &args[0])?;
                compile_expr(cg, &args[1])?;
                cg.emit(cmp);
                return Ok(());
            }
        }
    }
    compile_expr(cg, expr)?;
    cg.emit(Instruction::I64Const(0));
    cg.emit(Instruction::I64Ne); // → i32: 1 if non-zero
    Ok(())
}

/// The i32-producing wasm instruction for a 2-arg comparison builtin, or `None`
/// for anything else. Used by [`compile_truthy_i32`] to feed a comparison
/// straight into an `if`/`br_if` condition.
fn comparison_i32_instruction(op: Builtin) -> Option<Instruction<'static>> {
    Some(match op {
        Builtin::Eq => Instruction::I64Eq,
        Builtin::NotEq => Instruction::I64Ne,
        Builtin::Lt => Instruction::I64LtS,
        Builtin::Gt => Instruction::I64GtS,
        Builtin::Le => Instruction::I64LeS,
        Builtin::Ge => Instruction::I64GeS,
        _ => return None,
    })
}

fn compile_builtin(cg: &mut FnCtx, op: Builtin, args: &[Expr]) -> Result<(), CljError> {
    // Arithmetic on any float operand runs the whole op in f64 (int operands
    // promoted). `is_float_op` short-circuits to the integer paths below.
    let is_float_op = args.iter().any(|a| is_float_expr(a, &cg.float_env));
    match op {
        Builtin::Add if is_float_op => fold_f64(cg, args, Instruction::F64Add),
        Builtin::Mul if is_float_op => fold_f64(cg, args, Instruction::F64Mul),
        Builtin::Div if is_float_op => fold_f64(cg, args, Instruction::F64Div),
        Builtin::Sub if is_float_op => {
            if args.len() == 1 {
                // unary float negate: 0.0 - x
                cg.emit(Instruction::F64Const(0.0));
                compile_expr_as_f64(cg, &args[0])?;
                cg.emit(Instruction::F64Sub);
                cg.emit(Instruction::I64ReinterpretF64);
                Ok(())
            } else {
                fold_f64(cg, args, Instruction::F64Sub)
            }
        }

        Builtin::Add => fold(cg, args, Instruction::I64Add),
        Builtin::Mul => fold(cg, args, Instruction::I64Mul),
        Builtin::Sub => {
            if args.len() == 1 {
                // unary negate: 0 - x
                cg.emit(Instruction::I64Const(0));
                compile_expr(cg, &args[0])?;
                cg.emit(Instruction::I64Sub);
                Ok(())
            } else {
                fold(cg, args, Instruction::I64Sub)
            }
        }
        Builtin::Div => binop(cg, args, Instruction::I64DivS),
        Builtin::Rem => binop(cg, args, Instruction::I64RemS),
        Builtin::Mod => {
            // Clojure floored mod: ((a rem b) + b) rem b — result has the sign of b.
            // Evaluate a and b once into scratch locals (no side-effect duplication).
            compile_expr(cg, &args[0])?;
            let a = cg.alloc_local();
            cg.emit(Instruction::LocalSet(a));
            compile_expr(cg, &args[1])?;
            let bl = cg.alloc_local();
            cg.emit(Instruction::LocalSet(bl));
            cg.emit(Instruction::LocalGet(a));
            cg.emit(Instruction::LocalGet(bl));
            cg.emit(Instruction::I64RemS);
            cg.emit(Instruction::LocalGet(bl));
            cg.emit(Instruction::I64Add);
            cg.emit(Instruction::LocalGet(bl));
            cg.emit(Instruction::I64RemS);
            Ok(())
        }
        Builtin::Inc => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(1));
            cg.emit(Instruction::I64Add);
            Ok(())
        }
        Builtin::Dec => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(1));
            cg.emit(Instruction::I64Sub);
            Ok(())
        }
        Builtin::Abs => {
            compile_expr(cg, &args[0])?;
            let value = cg.alloc_local();
            cg.emit(Instruction::LocalSet(value));
            cg.emit(Instruction::LocalGet(value));
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64LtS);
            cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::LocalGet(value));
            cg.emit(Instruction::I64Sub);
            cg.emit(Instruction::Else);
            cg.emit(Instruction::LocalGet(value));
            cg.close_frame();
            Ok(())
        }
        Builtin::Min => compile_min_max(cg, args, true),
        Builtin::Max => compile_min_max(cg, args, false),

        // `(double x)` — int→f64 (promote) or float passthrough; the result
        // slot holds the IEEE-754 bits.
        Builtin::Double => {
            compile_expr_as_f64(cg, &args[0])?;
            cg.emit(Instruction::I64ReinterpretF64);
            Ok(())
        }
        // `(int x)` / `(long x)` — float→int truncate toward zero (saturating,
        // so a NaN/overflow yields a defined value instead of trapping); int
        // passthrough.
        Builtin::Int => {
            if is_float_expr(&args[0], &cg.float_env) {
                compile_expr_as_f64(cg, &args[0])?;
                cg.emit(Instruction::I64TruncSatF64S);
            } else {
                compile_expr(cg, &args[0])?;
            }
            Ok(())
        }
        // `(Math/round x)` — round to nearest, ties away from zero (Clojure):
        // `trunc(x + copysign(0.5, x))`. Emitted as `floor(x + 0.5)` for x≥0
        // and `ceil(x - 0.5)` for x<0, selected at runtime; result is an int.
        Builtin::MathRound => {
            // Stash the operand's f64 bits in an i64 local (all locals are i64;
            // we reinterpret on each read) so we can branch on its sign.
            compile_expr_as_f64(cg, &args[0])?;
            cg.emit(Instruction::I64ReinterpretF64);
            let bits = cg.alloc_local();
            cg.emit(Instruction::LocalSet(bits));
            // x >= 0 ?
            cg.emit(Instruction::LocalGet(bits));
            cg.emit(Instruction::F64ReinterpretI64);
            cg.emit(Instruction::F64Const(0.0));
            cg.emit(Instruction::F64Ge);
            cg.open_frame(Instruction::If(BlockType::Result(ValType::F64)));
            // floor(x + 0.5)
            cg.emit(Instruction::LocalGet(bits));
            cg.emit(Instruction::F64ReinterpretI64);
            cg.emit(Instruction::F64Const(0.5));
            cg.emit(Instruction::F64Add);
            cg.emit(Instruction::F64Floor);
            cg.emit(Instruction::Else);
            // ceil(x - 0.5)
            cg.emit(Instruction::LocalGet(bits));
            cg.emit(Instruction::F64ReinterpretI64);
            cg.emit(Instruction::F64Const(0.5));
            cg.emit(Instruction::F64Sub);
            cg.emit(Instruction::F64Ceil);
            cg.close_frame();
            cg.emit(Instruction::I64TruncSatF64S);
            Ok(())
        }
        // `(Math/floor x)` — f64 floor, yields a float (Clojure returns double).
        Builtin::MathFloor => {
            compile_expr_as_f64(cg, &args[0])?;
            cg.emit(Instruction::F64Floor);
            cg.emit(Instruction::I64ReinterpretF64);
            Ok(())
        }
        // `(Math/ceil x)` — f64 ceil, yields a float.
        Builtin::MathCeil => {
            compile_expr_as_f64(cg, &args[0])?;
            cg.emit(Instruction::F64Ceil);
            cg.emit(Instruction::I64ReinterpretF64);
            Ok(())
        }
        // `(Math/abs x)` — preserves float-ness: f64.abs for a float operand,
        // integer abs otherwise.
        Builtin::MathAbs => {
            if is_float_expr(&args[0], &cg.float_env) {
                compile_expr_as_f64(cg, &args[0])?;
                cg.emit(Instruction::F64Abs);
                cg.emit(Instruction::I64ReinterpretF64);
                Ok(())
            } else {
                compile_builtin(cg, Builtin::Abs, args)
            }
        }
        // `(Math/sqrt x)` — f64 square root, yields a float.
        Builtin::MathSqrt => {
            compile_expr_as_f64(cg, &args[0])?;
            cg.emit(Instruction::F64Sqrt);
            cg.emit(Instruction::I64ReinterpretF64);
            Ok(())
        }

        // Float comparisons: any float operand → compare the f64
        // interpretation (int operands promoted). `=`/`<`/`>`/`<=`/`>=` supported.
        Builtin::Eq if is_float_op => pairwise_cmp_f64(cg, args, Instruction::F64Eq),
        Builtin::Lt if is_float_op => pairwise_cmp_f64(cg, args, Instruction::F64Lt),
        Builtin::Gt if is_float_op => pairwise_cmp_f64(cg, args, Instruction::F64Gt),
        Builtin::Le if is_float_op => pairwise_cmp_f64(cg, args, Instruction::F64Le),
        Builtin::Ge if is_float_op => pairwise_cmp_f64(cg, args, Instruction::F64Ge),

        Builtin::Eq => pairwise_cmp(cg, args, Instruction::I64Eq),
        Builtin::NotEq => compile_not_eq(cg, args),
        Builtin::Lt => pairwise_cmp(cg, args, Instruction::I64LtS),
        Builtin::Gt => pairwise_cmp(cg, args, Instruction::I64GtS),
        Builtin::Le => pairwise_cmp(cg, args, Instruction::I64LeS),
        Builtin::Ge => pairwise_cmp(cg, args, Instruction::I64GeS),
        Builtin::Zero => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Eqz);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Some => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64Ne);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Pos => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64GtS);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Neg => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64LtS);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Even => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(1));
            cg.emit(Instruction::I64And);
            cg.emit(Instruction::I64Eqz);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Odd => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(1));
            cg.emit(Instruction::I64And);
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64Ne);
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }

        Builtin::Not => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Eqz); // → i32: 1 if zero
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::And => compile_and(cg, args),
        Builtin::Or => compile_or(cg, args),

        Builtin::BitAnd => fold(cg, args, Instruction::I64And),
        Builtin::BitOr => fold(cg, args, Instruction::I64Or),
        Builtin::BitXor => fold(cg, args, Instruction::I64Xor),
        Builtin::BitShiftLeft => binop(cg, args, Instruction::I64Shl),
        Builtin::BitShiftRight => binop(cg, args, Instruction::I64ShrS),

        // len = handle & 0xFFFF_FFFF
        Builtin::StrLen => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Const(0xFFFF_FFFF));
            cg.emit(Instruction::I64And);
            Ok(())
        }
        // byte = mem[(handle >>> 32) + i] as u8
        Builtin::ByteAt => {
            compile_expr(cg, &args[0])?; // handle
            cg.emit(Instruction::I64Const(32));
            cg.emit(Instruction::I64ShrU); // ptr (i64)
            compile_expr(cg, &args[1])?; // index (i64)
            cg.emit(Instruction::I64Add); // address (i64)
            cg.emit(Instruction::I32WrapI64); // address (i32)
            cg.emit(Instruction::I32Load8U(mem8(0)));
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }

        Builtin::BytesAlloc => compile_bytes_alloc(cg, &args[0]),
        Builtin::ByteAppend => compile_byte_append(cg, &args[0], &args[1]),
        // len = mem[buf + 4]  (the header's length field)
        Builtin::BytesLen => {
            compile_expr(cg, &args[0])?; // buf header ptr (i64)
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I32Load(mem32(4)));
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::BytesFinish => compile_bytes_finish(cg, &args[0]),

        // raw memory substrate (the dynamic-container prelude builds on these)
        Builtin::Alloc => {
            cg.emit(Instruction::I32Const(0));
            cg.emit(Instruction::I32Const(0));
            cg.emit(Instruction::I32Const(HEAP_ALIGN as i32));
            compile_expr(cg, &args[0])?; // n
            cg.emit(Instruction::I32WrapI64);
            let realloc = cg.realloc_index;
            cg.emit(Instruction::Call(realloc));
            cg.emit(Instruction::I64ExtendI32U); // ptr → i64
            Ok(())
        }
        Builtin::Load64 => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I64Load(mem64(0)));
            Ok(())
        }
        Builtin::Load32 => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I32WrapI64);
            cg.emit(Instruction::I32Load(mem32(0)));
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::Store64 => compile_store(cg, &args[0], &args[1], /*word32=*/ false),
        Builtin::Store32 => compile_store(cg, &args[0], &args[1], /*word32=*/ true),

        Builtin::HasCapability => compile_host_call(cg, HostImport::HasCapability, args),
        Builtin::LlmInfer => compile_llm_infer(cg, &args[0], &args[1]),
        Builtin::KqeAssert => compile_kqe_mutate(cg, HostImport::KqeAssertQuad, args),
        Builtin::KqeRetract => compile_kqe_mutate(cg, HostImport::KqeRetractQuad, args),
        Builtin::KqeGetObjects => compile_kqe_get_objects(cg, args),
        Builtin::KqeQuery => compile_kqe_query(cg, &args[0]),
    }
}

/// Lower `(kqe-assert!/kqe-retract! graph subject predicate object-cbor)` — a
/// host import taking the flattened `quad` record (4 × `(ptr,len)`) whose
/// `result<_, string>` return uses the indirect return-area ABI:
///   1. `cabi_realloc` a 12-byte area (align 4),
///   2. push the four fields as `(ptr,len)` pairs, then the area pointer,
///   3. `call` the import (no core result),
///   4. read `tag = mem[area]` → `1` on ok (tag 0), `0` on err.
fn compile_kqe_mutate(cg: &mut FnCtx, imp: HostImport, args: &[Expr]) -> Result<(), CljError> {
    let idx = *cg
        .import_index
        .get(&imp)
        .ok_or_else(|| CljError::Codegen(format!("host import {imp:?} not registered")))?;
    let realloc = cg.realloc_index;
    let area = cg.alloc_local();

    // area = cabi_realloc(0, 0, 4, 12)
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(4));
    cg.emit(Instruction::I32Const(12));
    cg.emit(Instruction::Call(realloc));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::LocalSet(area));

    // graph, subject, predicate, object-cbor — each as (ptr,len)
    for a in args {
        lower_string_arg_to_ptr_len(cg, a)?;
    }
    // return-area pointer (i32)
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::Call(idx));

    // tag == 0 (ok) → 1, else (err) → 0
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load8U(mem8(0)));
    cg.emit(Instruction::I32Eqz);
    cg.emit(Instruction::I64ExtendI32U);
    Ok(())
}

/// Lower `(kqe-get-objects graph subject predicate)` — the host lifts a
/// `list<list<u8>>` into guest memory (via our exported `cabi_realloc`) and
/// writes `[ptr @0, len @4]` into an 8-byte return area. The builtin yields a
/// packed list handle `(ptr << 32) | count`; elements (8 bytes each:
/// `[ptr,len]`) are read in-language via `load32` (see `KQE_PRELUDE`).
fn compile_kqe_get_objects(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    let idx = *cg
        .import_index
        .get(&HostImport::KqeGetObjects)
        .ok_or_else(|| CljError::Codegen("host import KqeGetObjects not registered".into()))?;
    let realloc = cg.realloc_index;
    let area = cg.alloc_local();

    // area = cabi_realloc(0, 0, 4, 8)
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(4));
    cg.emit(Instruction::I32Const(8));
    cg.emit(Instruction::Call(realloc));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::LocalSet(area));

    // graph, subject, predicate — each as (ptr,len)
    for a in args {
        lower_string_arg_to_ptr_len(cg, a)?;
    }
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::Call(idx));

    // handle = (mem[area] << 32) | mem[area+4]   (element-array ptr | count)
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(0)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Const(32));
    cg.emit(Instruction::I64Shl);
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Or);
    Ok(())
}

/// Lower `(kqe-query predicate-filter)` — same indirect `result<list<…>,
/// string>` tail as `llm.infer`, but the ok payload is a `list<quad>`: the
/// handle packs `(quad-array-ptr << 32) | count`, 32 bytes per quad (4 ×
/// `[ptr,len]` fields, read in-language via `load32`). `0` on err.
fn compile_kqe_query(cg: &mut FnCtx, filter: &Expr) -> Result<(), CljError> {
    let idx = *cg
        .import_index
        .get(&HostImport::KqeQuery)
        .ok_or_else(|| CljError::Codegen("host import KqeQuery not registered".into()))?;
    let realloc = cg.realloc_index;
    let area = cg.alloc_local();

    // area = cabi_realloc(0, 0, 4, 12)
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(4));
    cg.emit(Instruction::I32Const(12));
    cg.emit(Instruction::Call(realloc));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::LocalSet(area));

    lower_string_arg_to_ptr_len(cg, filter)?;
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::Call(idx));

    // tag == 0 ? (ptr << 32) | count : 0
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load8U(mem8(0)));
    cg.emit(Instruction::I32Eqz);
    cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Const(32));
    cg.emit(Instruction::I64Shl);
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(8)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Or);
    cg.emit(Instruction::Else);
    cg.emit(Instruction::I64Const(0));
    cg.close_frame();
    Ok(())
}

/// Lower `(llm-infer model-cid prompt)` — a host import whose
/// `result<list<u8>, string>` return uses the indirect **return-area** ABI:
///   1. `cabi_realloc` a 12-byte area (align 4),
///   2. push `model (ptr,len)`, `prompt (ptr,len)`, then the area pointer,
///   3. `call` the import (no core result),
///   4. read `tag = mem[area]`; on `ok` (tag 0) rebuild the output string handle
///      `(mem[area+4] << 32) | mem[area+8]`, on `err` yield `0`.
fn compile_llm_infer(cg: &mut FnCtx, model: &Expr, prompt: &Expr) -> Result<(), CljError> {
    let idx = *cg
        .import_index
        .get(&HostImport::LlmInfer)
        .ok_or_else(|| CljError::Codegen("host import LlmInfer not registered".into()))?;
    let realloc = cg.realloc_index;
    let area = cg.alloc_local(); // i64 local holding the area pointer (extended)

    // area = cabi_realloc(0, 0, 4, 12)
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(4));
    cg.emit(Instruction::I32Const(12));
    cg.emit(Instruction::Call(realloc));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::LocalSet(area));

    // model (ptr,len), prompt (ptr,len)
    lower_string_arg_to_ptr_len(cg, model)?;
    lower_string_arg_to_ptr_len(cg, prompt)?;
    // return-area pointer (i32)
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    // call — returns nothing; the host populated the return area
    cg.emit(Instruction::Call(idx));

    // tag == 0 ? ok : err
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load8U(mem8(0)));
    cg.emit(Instruction::I32Eqz); // 1 if tag == 0 (ok)
    cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
    // ok: handle = (mem[area+4] << 32) | mem[area+8]
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Const(32));
    cg.emit(Instruction::I64Shl);
    cg.emit(Instruction::LocalGet(area));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(8)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Or);
    cg.emit(Instruction::Else);
    // err: nil-ish 0 (an empty string handle: ptr 0, len 0)
    cg.emit(Instruction::I64Const(0));
    cg.close_frame();
    Ok(())
}

/// Lower a host-import call. Each string-handle argument is unpacked into its
/// `(ptr: i32, len: i32)` pair (the Canonical-ABI lowering of `string`), pushed
/// left-to-right, then the imported function is `call`ed. The single i32 result
/// (a `bool`) is zero-extended back to the uniform i64 value model.
fn compile_host_call(cg: &mut FnCtx, imp: HostImport, args: &[Expr]) -> Result<(), CljError> {
    let idx = *cg
        .import_index
        .get(&imp)
        .ok_or_else(|| CljError::Codegen(format!("host import {imp:?} not registered")))?;
    for a in args {
        lower_string_arg_to_ptr_len(cg, a)?;
    }
    cg.emit(Instruction::Call(idx));
    cg.emit(Instruction::I64ExtendI32U); // bool i32 → i64
    Ok(())
}

/// Push a string handle's `(ptr: i32, len: i32)` as two stack operands, in that
/// order — the flattened form a `string` lowers to when passed to a host call.
fn lower_string_arg_to_ptr_len(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    let h = cg.alloc_local();
    compile_expr(cg, expr)?; // i64 handle
    cg.emit(Instruction::LocalSet(h));
    // ptr = handle >>> 32
    cg.emit(Instruction::LocalGet(h));
    cg.emit(Instruction::I64Const(32));
    cg.emit(Instruction::I64ShrU);
    cg.emit(Instruction::I32WrapI64);
    // len = handle & 0xFFFF_FFFF
    cg.emit(Instruction::LocalGet(h));
    cg.emit(Instruction::I64Const(0xFFFF_FFFF));
    cg.emit(Instruction::I64And);
    cg.emit(Instruction::I32WrapI64);
    Ok(())
}

/// `(store64!/store32! addr val)` — write `val` at `addr`, then leave `val` on
/// the stack so the write threads through `do`/`recur`.
fn compile_store(cg: &mut FnCtx, addr: &Expr, val: &Expr, word32: bool) -> Result<(), CljError> {
    let val_l = cg.alloc_local();
    compile_expr(cg, val)?;
    cg.emit(Instruction::LocalSet(val_l));
    compile_expr(cg, addr)?;
    cg.emit(Instruction::I32WrapI64); // addr (i32)
    cg.emit(Instruction::LocalGet(val_l));
    if word32 {
        cg.emit(Instruction::I32WrapI64);
        cg.emit(Instruction::I32Store(mem32(0)));
    } else {
        cg.emit(Instruction::I64Store(mem64(0)));
    }
    cg.emit(Instruction::LocalGet(val_l)); // → val
    Ok(())
}

/// A 4-byte-aligned i32 access MemArg at `offset`.
fn mem32(offset: u64) -> MemArg {
    MemArg {
        offset,
        align: 2,
        memory_index: 0,
    }
}
/// An unaligned single-byte access MemArg at `offset`.
fn mem8(offset: u64) -> MemArg {
    MemArg {
        offset,
        align: 0,
        memory_index: 0,
    }
}
/// An 8-byte-aligned i64 access MemArg at `offset`.
fn mem64(offset: u64) -> MemArg {
    MemArg {
        offset,
        align: 3,
        memory_index: 0,
    }
}

/// A byte buffer is an 8-byte header `[cap:i32 @0, len:i32 @4]` followed by
/// `cap` data bytes; its *handle* is the i64 value of the header pointer. This
/// is deliberately distinct from a string handle (which packs `ptr<<32|len`):
/// builder ops take buffer handles, `str-len`/`byte-at` take string handles,
/// and `bytes-finish` converts the former to the latter.
const BUF_HEADER: i32 = 8;

/// `(bytes-alloc cap)` → `cabi_realloc(0,0,16, cap+8)`, write `[cap, 0]`, return
/// the header pointer as an i64 buffer handle.
fn compile_bytes_alloc(cg: &mut FnCtx, cap_expr: &Expr) -> Result<(), CljError> {
    let cap_l = cg.alloc_local();
    let ptr_l = cg.alloc_local();

    compile_expr(cg, cap_expr)?; // i64 cap
    cg.emit(Instruction::LocalSet(cap_l));

    // ptr = cabi_realloc(old=0, old_sz=0, align=16, new_sz=cap+8)
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Const(HEAP_ALIGN as i32));
    cg.emit(Instruction::LocalGet(cap_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Const(BUF_HEADER));
    cg.emit(Instruction::I32Add); // new_sz = cap + 8
    let realloc = cg.realloc_index;
    cg.emit(Instruction::Call(realloc));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::LocalSet(ptr_l)); // ptr_l = header ptr (i64)

    // header[0] = cap
    cg.emit(Instruction::LocalGet(ptr_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::LocalGet(cap_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Store(mem32(0)));
    // header[4] = 0 (len)
    cg.emit(Instruction::LocalGet(ptr_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Const(0));
    cg.emit(Instruction::I32Store(mem32(4)));

    cg.emit(Instruction::LocalGet(ptr_l)); // → buffer handle
    Ok(())
}

/// `(byte-append! buf b)` — write `b & 0xFF` at `buf+8+len`, bump `len`, return
/// `buf`. No capacity check in this phase (the caller sizes via `bytes-alloc`).
fn compile_byte_append(cg: &mut FnCtx, buf_expr: &Expr, b_expr: &Expr) -> Result<(), CljError> {
    let buf_l = cg.alloc_local();
    let val_l = cg.alloc_local();

    compile_expr(cg, buf_expr)?;
    cg.emit(Instruction::LocalSet(buf_l));
    compile_expr(cg, b_expr)?;
    cg.emit(Instruction::LocalSet(val_l));

    // data address = (buf as i32) + 8 + len  ; len = mem[buf+4]
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Const(BUF_HEADER));
    cg.emit(Instruction::I32Add);
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4))); // len
    cg.emit(Instruction::I32Add); // addr = buf+8+len
                                  // value byte
    cg.emit(Instruction::LocalGet(val_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Store8(mem8(0))); // mem[addr] = b

    // mem[buf+4] = len + 1
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4)));
    cg.emit(Instruction::I32Const(1));
    cg.emit(Instruction::I32Add);
    cg.emit(Instruction::I32Store(mem32(4)));

    cg.emit(Instruction::LocalGet(buf_l)); // → buffer handle (unchanged)
    Ok(())
}

/// `(bytes-finish buf)` → string handle `((buf+8) << 32) | len` so the data
/// region reads back through `str-len`/`byte-at`.
fn compile_bytes_finish(cg: &mut FnCtx, buf_expr: &Expr) -> Result<(), CljError> {
    let buf_l = cg.alloc_local();
    compile_expr(cg, buf_expr)?;
    cg.emit(Instruction::LocalSet(buf_l));

    // (data_ptr << 32) where data_ptr = buf + 8
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I64Const(BUF_HEADER as i64));
    cg.emit(Instruction::I64Add);
    cg.emit(Instruction::I64Const(32));
    cg.emit(Instruction::I64Shl);
    // | len   (len = mem[buf+4], zero-extended)
    cg.emit(Instruction::LocalGet(buf_l));
    cg.emit(Instruction::I32WrapI64);
    cg.emit(Instruction::I32Load(mem32(4)));
    cg.emit(Instruction::I64ExtendI32U);
    cg.emit(Instruction::I64Or);
    Ok(())
}

// ── f64 floating-point support ──────────────────────────────────────────────
//
// The value model has a single 64-bit slot per value (everything is an `i64`
// on the operand stack). A float occupies that slot as its IEEE-754 **bit
// pattern**; there is no runtime tag. "Is this value a float?" is therefore
// answered *statically*, per-expression, by [`is_float_expr`]. Arithmetic and
// comparison builtins inspect their operands: if any operand is statically a
// float, the whole operation runs on the f64 interpretation (int operands are
// promoted with `f64.convert_i64_s`) and — for arithmetic — the f64 result is
// repacked into the i64 slot with `i64.reinterpret_f64`.

/// Statically decide whether `expr` evaluates to a float value (an IEEE-754 bit
/// pattern in the i64 slot) rather than an integer/handle. Conservative: only
/// forms whose float-ness is statically certain return `true`. Anything else
/// (variables, calls, host ops, closures) is treated as an integer — mixing a
/// runtime-float-bearing variable into float math is out of R0 scope and would
/// need a runtime tag.
fn is_float_expr(expr: &Expr, env: &FloatEnv) -> bool {
    match expr {
        Expr::Float(_) => true,
        // A named symbol is float if the env records it as float — either a
        // `def` global or a `let`/`loop` binding whose init was a float.
        Expr::Var(name) => env.is_float(name),
        Expr::Builtin { op, args } => match op {
            // Coercions whose result is a float by construction.
            Builtin::Double | Builtin::MathFloor | Builtin::MathCeil | Builtin::MathSqrt => true,
            // Arithmetic is float iff any operand is float (mixed int/float promotes).
            Builtin::Add | Builtin::Sub | Builtin::Mul | Builtin::Div => {
                args.iter().any(|a| is_float_expr(a, env))
            }
            // `(Math/abs x)` preserves the operand's float-ness.
            Builtin::MathAbs => args.first().map(|a| is_float_expr(a, env)).unwrap_or(false),
            _ => false,
        },
        // `(if c a b)` is float iff both branches are float.
        Expr::If { then, els, .. } => is_float_expr(then, env) && is_float_expr(els, env),
        _ => false,
    }
}

/// Compile `expr`, leaving an **f64** on the operand stack (not the packed i64
/// slot). A statically-float expr is compiled then `f64.reinterpret_i64`'d back
/// from its bit pattern; an integer expr is converted with `f64.convert_i64_s`
/// (int→float promotion for mixed arithmetic).
fn compile_expr_as_f64(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    if is_float_expr(expr, &cg.float_env) {
        compile_expr(cg, expr)?;
        cg.emit(Instruction::F64ReinterpretI64);
    } else {
        compile_expr(cg, expr)?;
        cg.emit(Instruction::F64ConvertI64S);
    }
    Ok(())
}

/// Fold a non-empty arg list with an f64 binary instruction, repacking the f64
/// result into the i64 slot via `i64.reinterpret_f64`.
fn fold_f64(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    compile_expr_as_f64(cg, &args[0])?;
    for a in &args[1..] {
        compile_expr_as_f64(cg, a)?;
        cg.emit(ins.clone());
    }
    cg.emit(Instruction::I64ReinterpretF64);
    Ok(())
}

/// Left-fold a non-empty arg list with a binary instruction.
fn fold(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    compile_expr(cg, &args[0])?;
    for a in &args[1..] {
        compile_expr(cg, a)?;
        cg.emit(ins.clone());
    }
    Ok(())
}

fn binop(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    compile_expr(cg, &args[0])?;
    compile_expr(cg, &args[1])?;
    cg.emit(ins);
    Ok(())
}

fn compile_min_max(cg: &mut FnCtx, args: &[Expr], is_min: bool) -> Result<(), CljError> {
    compile_expr(cg, &args[0])?;
    if args.len() == 1 {
        return Ok(());
    }

    let best = cg.alloc_local();
    let cur = cg.alloc_local();
    cg.emit(Instruction::LocalSet(best));

    for arg in &args[1..] {
        compile_expr(cg, arg)?;
        cg.emit(Instruction::LocalSet(cur));

        cg.emit(Instruction::LocalGet(cur));
        cg.emit(Instruction::LocalGet(best));
        cg.emit(if is_min {
            Instruction::I64LtS
        } else {
            Instruction::I64GtS
        });
        cg.open_frame(Instruction::If(BlockType::Empty));
        cg.emit(Instruction::LocalGet(cur));
        cg.emit(Instruction::LocalSet(best));
        cg.close_frame();
    }

    cg.emit(Instruction::LocalGet(best));
    Ok(())
}

/// Comparison: two i64 operands → i32 result, extended back to i64 (1/0).
fn cmp(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    compile_expr(cg, &args[0])?;
    compile_expr(cg, &args[1])?;
    cg.emit(ins);
    cg.emit(Instruction::I64ExtendI32U);
    Ok(())
}

/// Clojure-style n-ary comparisons. A single operand is vacuously true; with
/// more operands every adjacent pair must satisfy the comparison.
fn pairwise_cmp(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    if args.len() == 1 {
        cg.emit(Instruction::I64Const(1));
        return Ok(());
    }
    if args.len() == 2 {
        return cmp(cg, args, ins);
    }

    let prev = cg.alloc_local();
    let cur = cg.alloc_local();
    let acc = cg.alloc_local();
    compile_expr(cg, &args[0])?;
    cg.emit(Instruction::LocalSet(prev));
    cg.emit(Instruction::I64Const(1));
    cg.emit(Instruction::LocalSet(acc));

    for arg in &args[1..] {
        compile_expr(cg, arg)?;
        cg.emit(Instruction::LocalSet(cur));

        cg.emit(Instruction::LocalGet(acc));
        cg.emit(Instruction::I64Const(0));
        cg.emit(Instruction::I64Ne);
        cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
        cg.emit(Instruction::LocalGet(prev));
        cg.emit(Instruction::LocalGet(cur));
        cg.emit(ins.clone());
        cg.emit(Instruction::I64ExtendI32U);
        cg.emit(Instruction::Else);
        cg.emit(Instruction::I64Const(0));
        cg.close_frame();
        cg.emit(Instruction::LocalSet(acc));

        cg.emit(Instruction::LocalGet(cur));
        cg.emit(Instruction::LocalSet(prev));
    }

    cg.emit(Instruction::LocalGet(acc));
    Ok(())
}

/// f64 sibling of [`pairwise_cmp`]: each operand is compiled as an f64 (int
/// operands promoted), `ins` is an `f64.*` comparison producing i32 0/1, and
/// the i64 result is the 0/1 boolean in the uniform slot. n-ary chains store
/// the rolling `prev`/`cur` operands as their f64 bit pattern in i64 locals.
fn pairwise_cmp_f64(
    cg: &mut FnCtx,
    args: &[Expr],
    ins: Instruction<'static>,
) -> Result<(), CljError> {
    if args.len() == 1 {
        cg.emit(Instruction::I64Const(1));
        return Ok(());
    }
    if args.len() == 2 {
        compile_expr_as_f64(cg, &args[0])?;
        compile_expr_as_f64(cg, &args[1])?;
        cg.emit(ins);
        cg.emit(Instruction::I64ExtendI32U);
        return Ok(());
    }

    let prev = cg.alloc_local();
    let cur = cg.alloc_local();
    let acc = cg.alloc_local();
    // store f64 operands as their bit pattern (locals are i64).
    compile_expr_as_f64(cg, &args[0])?;
    cg.emit(Instruction::I64ReinterpretF64);
    cg.emit(Instruction::LocalSet(prev));
    cg.emit(Instruction::I64Const(1));
    cg.emit(Instruction::LocalSet(acc));

    for arg in &args[1..] {
        compile_expr_as_f64(cg, arg)?;
        cg.emit(Instruction::I64ReinterpretF64);
        cg.emit(Instruction::LocalSet(cur));

        cg.emit(Instruction::LocalGet(acc));
        cg.emit(Instruction::I64Const(0));
        cg.emit(Instruction::I64Ne);
        cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
        cg.emit(Instruction::LocalGet(prev));
        cg.emit(Instruction::F64ReinterpretI64);
        cg.emit(Instruction::LocalGet(cur));
        cg.emit(Instruction::F64ReinterpretI64);
        cg.emit(ins.clone());
        cg.emit(Instruction::I64ExtendI32U);
        cg.emit(Instruction::Else);
        cg.emit(Instruction::I64Const(0));
        cg.close_frame();
        cg.emit(Instruction::LocalSet(acc));

        cg.emit(Instruction::LocalGet(cur));
        cg.emit(Instruction::LocalSet(prev));
    }

    cg.emit(Instruction::LocalGet(acc));
    Ok(())
}

/// Clojure `not=` means pairwise distinct for all operands.
fn compile_not_eq(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    if args.len() == 1 {
        cg.emit(Instruction::I64Const(1));
        return Ok(());
    }
    let values = args
        .iter()
        .map(|arg| {
            compile_expr(cg, arg)?;
            let local = cg.alloc_local();
            cg.emit(Instruction::LocalSet(local));
            Ok(local)
        })
        .collect::<Result<Vec<_>, CljError>>()?;
    let acc = cg.alloc_local();
    cg.emit(Instruction::I64Const(1));
    cg.emit(Instruction::LocalSet(acc));

    for i in 0..values.len() {
        for j in (i + 1)..values.len() {
            cg.emit(Instruction::LocalGet(acc));
            cg.emit(Instruction::I64Const(0));
            cg.emit(Instruction::I64Ne);
            cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
            cg.emit(Instruction::LocalGet(values[i]));
            cg.emit(Instruction::LocalGet(values[j]));
            cg.emit(Instruction::I64Ne);
            cg.emit(Instruction::I64ExtendI32U);
            cg.emit(Instruction::Else);
            cg.emit(Instruction::I64Const(0));
            cg.close_frame();
            cg.emit(Instruction::LocalSet(acc));
        }
    }

    cg.emit(Instruction::LocalGet(acc));
    Ok(())
}

/// Short-circuit `and` with Clojure value-return semantics.
///
/// Clojure: `(and a b c)` returns the first falsy value, or the last value if
/// all are truthy.  It does NOT normalise to a 0/1 boolean.
///
/// **Value model note**: in kotoba-clj every i64 value is either a number, a
/// string handle, or the `false`/`nil` sentinel `0`.  The truthiness check
/// (`expr != 0`) therefore treats integer `0` as falsy — the same as Clojure
/// `false`/`nil`.  Integer `0` cannot be distinguished from `false` without an
/// additional tag bit, which is outside the current value-model scope.
fn compile_and(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    if args.len() == 1 {
        // Single-operand: return the value itself (truthy or not).
        return compile_expr(cg, &args[0]);
    }
    // Evaluate the first arg and store its value in a local so we can both
    // test its truthiness *and* return it when it is falsy.
    compile_expr(cg, &args[0])?;
    let tmp = cg.alloc_local();
    cg.emit(Instruction::LocalTee(tmp));
    // truthy test: tmp != 0  (i32 for the wasm `if` condition)
    cg.emit(Instruction::I64Const(0));
    cg.emit(Instruction::I64Ne);
    cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
    // if truthy: evaluate the rest; that result is the return value of `and`
    compile_and(cg, &args[1..])?;
    cg.emit(Instruction::Else);
    // if falsy: return the VALUE of this (falsy) operand, not a hardcoded 0
    cg.emit(Instruction::LocalGet(tmp));
    cg.close_frame();
    Ok(())
}

/// Short-circuit `or` with Clojure value-return semantics.
///
/// Clojure: `(or a b c)` returns the first truthy value, or the last value if
/// all are falsy.  It does NOT normalise to a 0/1 boolean.
///
/// **Value model note**: the same `0 == falsy` caveat as `compile_and` applies.
fn compile_or(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    if args.len() == 1 {
        // Single-operand: return the value itself.
        return compile_expr(cg, &args[0]);
    }
    // Evaluate the first arg and tee its value into a local.
    compile_expr(cg, &args[0])?;
    let tmp = cg.alloc_local();
    cg.emit(Instruction::LocalTee(tmp));
    // truthy test: tmp != 0  (i32 for the wasm `if` condition)
    cg.emit(Instruction::I64Const(0));
    cg.emit(Instruction::I64Ne);
    cg.open_frame(Instruction::If(BlockType::Result(ValType::I64)));
    // if truthy: return the VALUE of this operand (not a hardcoded 1)
    cg.emit(Instruction::LocalGet(tmp));
    cg.emit(Instruction::Else);
    // if falsy: evaluate the rest; that result is the return value of `or`
    compile_or(cg, &args[1..])?;
    cg.close_frame();
    Ok(())
}

// ---- compile-time constant evaluation (for `def`) ---------------------------

/// Evaluate all `def` constants to i64 values.
///
/// String-literal `def`s (e.g. `(def ^:private S "abc")`) are allowed: their
/// value is the packed string handle `(abs_offset << 32) | len` computed from
/// Build the set of `def` names whose initialiser is a float expression.
/// Defs are processed in order (sequential binding semantics): each new def
/// sees the float-types of the preceding ones.
fn float_def_names(program: &Program) -> HashSet<String> {
    let mut float_defs: HashSet<String> = HashSet::new();
    for d in &program.defs {
        let env = FloatEnv::new(float_defs.clone());
        if is_float_expr(&d.value, &env) {
            float_defs.insert(d.name.clone());
        }
    }
    float_defs
}

/// the already-interned [`Literals`] table.  This lets a `def`-bound name be
/// resolved at every use site by the normal `Var` path in [`compile_expr`],
/// just like an integer constant.
fn eval_consts(program: &Program, literals: &Literals) -> Result<HashMap<String, i64>, CljError> {
    let mut consts = HashMap::new();
    for d in &program.defs {
        let v = eval_const(&d.value, &consts, literals)?;
        consts.insert(d.name.clone(), v);
    }
    Ok(consts)
}

fn eval_const(
    expr: &Expr,
    consts: &HashMap<String, i64>,
    literals: &Literals,
) -> Result<i64, CljError> {
    Ok(match expr {
        Expr::Int(i) => *i,
        // A float `def` initialiser stores the f64 bit pattern as its constant
        // i64 slot value; references emit it verbatim (the float bits) and
        // float-arithmetic sites reinterpret. Constant-float folding (e.g.
        // `(def x (* 2.0 3.0))`) is deferred — see `eval_const_builtin`.
        Expr::Float(f) => f.to_bits() as i64,
        Expr::Str(bytes) => {
            // A string-literal `def` is allowed.  Resolve the handle from the
            // interned literals blob (populated by `collect_literals` before us).
            literals.handle(bytes).ok_or_else(|| {
                CljError::Codegen(
                    "string literal in `def` was not interned (internal error)".into(),
                )
            })?
        }
        Expr::Var(name) => *consts
            .get(name)
            .ok_or_else(|| CljError::Codegen(format!("def references non-constant `{name}`")))?,
        Expr::If { cond, then, els } => {
            if eval_const(cond, consts, literals)? != 0 {
                eval_const(then, consts, literals)?
            } else {
                eval_const(els, consts, literals)?
            }
        }
        Expr::Builtin { op, args } => {
            let v: Vec<i64> = args
                .iter()
                .map(|a| eval_const(a, consts, literals))
                .collect::<Result<_, _>>()?;
            eval_const_builtin(*op, &v)?
        }
        Expr::Do(body) => eval_const(body.last().unwrap(), consts, literals)?,
        Expr::Let { .. } => {
            return Err(CljError::Codegen(
                "`let` is not supported in a `def` initialiser".into(),
            ))
        }
        Expr::Loop { .. } | Expr::Recur(_) => {
            return Err(CljError::Codegen(
                "`loop`/`recur` are not supported in a `def` initialiser".into(),
            ))
        }
        Expr::Call { name, .. } => {
            return Err(CljError::Codegen(format!(
                "`def` initialiser cannot call function `{name}` (must be a compile-time constant)"
            )))
        }
        Expr::Fn { .. } | Expr::MakeClosure { .. } | Expr::ClosureRef(_) | Expr::CallValue { .. } => {
            return Err(CljError::Codegen(
                "anonymous functions / closures are not allowed in a `def` initialiser (must be a compile-time constant)".into(),
            ))
        }
    })
}

fn eval_const_builtin(op: Builtin, v: &[i64]) -> Result<i64, CljError> {
    let b = |x: bool| if x { 1 } else { 0 };
    Ok(match op {
        Builtin::Add => v.iter().sum(),
        Builtin::Mul => v.iter().product(),
        Builtin::Sub if v.len() == 1 => -v[0],
        Builtin::Sub => v[1..].iter().fold(v[0], |a, x| a - x),
        Builtin::Div => v[0]
            .checked_div(v[1])
            .ok_or_else(|| CljError::Codegen("division by zero in const".into()))?,
        Builtin::Rem => v[0]
            .checked_rem(v[1])
            .ok_or_else(|| CljError::Codegen("rem by zero in const".into()))?,
        Builtin::Mod => {
            // floored: ((a rem b) + b) rem b — matches the runtime + Clojure semantics
            let r = v[0]
                .checked_rem(v[1])
                .ok_or_else(|| CljError::Codegen("mod by zero in const".into()))?;
            (r + v[1]) % v[1]
        }
        Builtin::Inc => v[0] + 1,
        Builtin::Dec => v[0] - 1,
        Builtin::Abs => v[0].abs(),
        Builtin::Min => *v.iter().min().expect("min arity checked"),
        Builtin::Max => *v.iter().max().expect("max arity checked"),
        Builtin::Eq => b(v.windows(2).all(|pair| pair[0] == pair[1])),
        Builtin::NotEq => b(v
            .iter()
            .enumerate()
            .all(|(i, x)| v.iter().skip(i + 1).all(|y| x != y))),
        Builtin::Lt => b(v.windows(2).all(|pair| pair[0] < pair[1])),
        Builtin::Gt => b(v.windows(2).all(|pair| pair[0] > pair[1])),
        Builtin::Le => b(v.windows(2).all(|pair| pair[0] <= pair[1])),
        Builtin::Ge => b(v.windows(2).all(|pair| pair[0] >= pair[1])),
        Builtin::Zero => b(v[0] == 0),
        Builtin::Some => b(v[0] != 0),
        Builtin::Pos => b(v[0] > 0),
        Builtin::Neg => b(v[0] < 0),
        Builtin::Even => b(v[0] & 1 == 0),
        Builtin::Odd => b(v[0] & 1 != 0),
        Builtin::Not => b(v[0] == 0),
        // `and`/`or` return values (Clojure semantics), not booleans.
        // `and`: first falsy value, or the last value when all truthy.
        Builtin::And => {
            let mut result = 1i64; // identity for `and` with zero args (vacuously true)
            for &x in v.iter() {
                result = x;
                if x == 0 {
                    break;
                }
            }
            result
        }
        // `or`: first truthy value, or the last value when all falsy.
        Builtin::Or => {
            let mut result = 0i64; // identity for `or` with zero args (vacuously false)
            for &x in v.iter() {
                result = x;
                if x != 0 {
                    break;
                }
            }
            result
        }
        Builtin::BitAnd => v.iter().copied().reduce(|a, b| a & b).unwrap_or(0),
        Builtin::BitOr => v.iter().copied().reduce(|a, b| a | b).unwrap_or(0),
        Builtin::BitXor => v.iter().copied().reduce(|a, b| a ^ b).unwrap_or(0),
        Builtin::BitShiftLeft => v[0].wrapping_shl(v[1] as u32),
        Builtin::BitShiftRight => v[0].wrapping_shr(v[1] as u32),
        Builtin::StrLen
        | Builtin::ByteAt
        | Builtin::BytesAlloc
        | Builtin::ByteAppend
        | Builtin::BytesLen
        | Builtin::BytesFinish
        | Builtin::Alloc
        | Builtin::Load64
        | Builtin::Store64
        | Builtin::Load32
        | Builtin::Store32 => {
            return Err(CljError::Codegen(
                "string/bytes/memory operations are not allowed in a `def` initialiser".into(),
            ))
        }
        Builtin::HasCapability
        | Builtin::LlmInfer
        | Builtin::KqeAssert
        | Builtin::KqeRetract
        | Builtin::KqeGetObjects
        | Builtin::KqeQuery => {
            return Err(CljError::Codegen(
                "host calls are not allowed in a `def` initialiser".into(),
            ))
        }
        // Float coercions in a compile-time-constant `def` are not folded yet
        // (the const evaluator is integer-only). Use them in function bodies.
        Builtin::Double
        | Builtin::Int
        | Builtin::MathRound
        | Builtin::MathFloor
        | Builtin::MathCeil
        | Builtin::MathAbs
        | Builtin::MathSqrt => {
            return Err(CljError::Codegen(
                "float coercions are not yet supported in a `def` initialiser \
                 (use them inside a function body)"
                    .into(),
            ))
        }
    })
}
