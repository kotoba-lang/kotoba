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
//! Every value on the operand stack is an `i64`. Two interpretations:
//!   - **number / boolean**: the i64 is the value; booleans are `1`/`0`, truthy
//!     ⇔ non-zero.
//!   - **string handle**: a packed `(offset << 32) | (len & 0xFFFF_FFFF)` where
//!     `offset` is a byte offset into linear memory and `len` the byte length.
//!     `str-len` / `byte-at` operate on this handle.
//!
//! ## Memory substrate (Step 1/2 of the kotoba:kais roadmap)
//!
//! Every emitted module exports:
//!   - `memory`        — a single linear memory.
//!   - `cabi_realloc`  — the Canonical-ABI bump allocator the Component Model
//!                       host calls to place lowered values into guest memory.
//!
//! String literals are laid out in an active data segment starting at
//! [`DATA_BASE`]; the bump heap starts immediately above them. This is the
//! linear-memory foundation that the future `list<u8>` Component export and
//! CBOR `InvokeContext` decode will build on (see `docs/ADR-clojure-wasm.md`).

use std::collections::HashMap;

use wasm_encoder::{
    BlockType, CodeSection, ConstExpr, DataSection, ExportKind, ExportSection, Function,
    FunctionSection, GlobalSection, GlobalType, Instruction, MemArg, MemorySection, MemoryType,
    Module, TypeSection, ValType,
};

use crate::ast::{Builtin, Expr, Program};
use crate::CljError;

/// Byte offset where string/data literals begin. Low memory `[0, DATA_BASE)` is
/// left as a null/scratch guard region.
const DATA_BASE: u32 = 1024;
/// Bump-heap alignment for `cabi_realloc` returns and the heap base.
const HEAP_ALIGN: u32 = 16;
const WASM_PAGE: u32 = 65536;

/// Compile a parsed [`Program`] into WebAssembly bytes (core module; every
/// `defn` exported by name).
pub fn compile(program: &Program) -> Result<Vec<u8>, CljError> {
    compile_core(program, None)
}

/// The Canonical-ABI shape of the generated `run` entry wrapper's return value.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EntryAbi {
    /// `run: func(list<u8>) -> list<u8>` — 8-byte return area `[ptr, len]`.
    BytesToBytes,
    /// `run: func(list<u8>) -> result<list<u8>, string>` — always `ok`; 12-byte
    /// return area `[tag:u8 @0, ptr:i32 @4, len:i32 @8]` (the kotoba-node shape).
    BytesToResultBytes,
}

/// A component entry point: the user `defn` to wrap and the ABI of its export.
#[derive(Debug, Clone, Copy)]
pub struct Entry<'a> {
    pub name: &'a str,
    pub abi: EntryAbi,
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
pub fn compile_core(program: &Program, entry: Option<Entry>) -> Result<Vec<u8>, CljError> {
    // ---- Pass 0: collect string literals into one data blob ----------------
    let literals = collect_literals(program);

    // ---- Pass 1: constants + function signatures ---------------------------
    let consts = eval_consts(program)?;

    let mut fn_index: HashMap<String, (u32, usize)> = HashMap::new();
    for (i, f) in program.functions.iter().enumerate() {
        if fn_index.contains_key(&f.name) {
            return Err(CljError::Codegen(format!("function `{}` defined twice", f.name)));
        }
        fn_index.insert(f.name.clone(), (i as u32, f.params.len()));
    }

    // Validate the entry point up front.
    let entry_target = match entry {
        Some(Entry { name, abi }) => {
            let (idx, arity) = fn_index.get(name).copied().ok_or_else(|| {
                CljError::Codegen(format!("component entry `(defn {name} [input] …)` not found"))
            })?;
            if arity != 1 {
                return Err(CljError::Codegen(format!(
                    "component entry `{name}` must take exactly 1 argument (the input bytes), got {arity}"
                )));
            }
            Some((idx, abi))
        }
        None => None,
    };

    // Distinct function types, keyed by arity (params: arity×i64 → i64).
    let mut types = TypeSection::new();
    let mut type_for_arity: HashMap<usize, u32> = HashMap::new();
    let mut funcs = FunctionSection::new();
    let mut exports = ExportSection::new();
    for (i, f) in program.functions.iter().enumerate() {
        let arity = f.params.len();
        let type_idx = *type_for_arity.entry(arity).or_insert_with(|| {
            let idx = types.len();
            types
                .ty()
                .function(std::iter::repeat(ValType::I64).take(arity), [ValType::I64]);
            idx
        });
        funcs.function(type_idx);
        // In component mode the wrapper owns the export names; don't leak the
        // raw i64 functions (avoids a clash on the `run` name).
        if entry.is_none() {
            exports.export(&f.name, ExportKind::Func, i as u32);
        }
    }

    // cabi_realloc: (old:i32, old_sz:i32, align:i32, new_sz:i32) -> i32
    let realloc_type = types.len();
    types.ty().function(
        [ValType::I32, ValType::I32, ValType::I32, ValType::I32],
        [ValType::I32],
    );
    let realloc_fn_index = program.functions.len() as u32;
    funcs.function(realloc_type);
    exports.export("cabi_realloc", ExportKind::Func, realloc_fn_index);

    // Canonical-ABI `run` wrapper (only in component mode).
    if let Some((user_idx, _abi)) = entry_target {
        let wrapper_type = types.len();
        types
            .ty()
            .function([ValType::I32, ValType::I32], [ValType::I32]);
        funcs.function(wrapper_type);
        let wrapper_index = realloc_fn_index + 1;
        exports.export("run", ExportKind::Func, wrapper_index);
        // user_idx / realloc_fn_index captured for the code section below.
        debug_assert!(user_idx < realloc_fn_index);
    }

    // ---- Memory + heap global ----------------------------------------------
    let heap_start = align_up(DATA_BASE + literals.blob.len() as u32, HEAP_ALIGN);
    let min_pages = heap_start.div_ceil(WASM_PAGE).max(1) as u64;

    let mut memories = MemorySection::new();
    memories.memory(MemoryType {
        minimum: min_pages,
        maximum: None,
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
            literals: &literals,
            scope: f
                .params
                .iter()
                .enumerate()
                .map(|(i, p)| (p.clone(), i as u32))
                .collect(),
            next_local: f.params.len() as u32,
            arity: f.params.len() as u32,
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
    if let Some((user_idx, abi)) = entry_target {
        code.function(&entry_wrapper_fn(user_idx, realloc_fn_index, abi));
    }

    // ---- Data segment -------------------------------------------------------
    let mut data = DataSection::new();
    if !literals.blob.is_empty() {
        data.active(0, &ConstExpr::i32_const(DATA_BASE as i32), literals.blob.iter().copied());
    }

    // Sections must be emitted in ascending id order.
    let mut module = Module::new();
    module.section(&types); // 1
    module.section(&funcs); // 3
    module.section(&memories); // 5
    module.section(&globals); // 6
    module.section(&exports); // 7
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
        Expr::Int(_) | Expr::Var(_) => {}
        Expr::If { cond, then, els } => {
            walk_strings(cond, f);
            walk_strings(then, f);
            walk_strings(els, f);
        }
        Expr::Let { bindings, body } => {
            for (_, v) in bindings {
                walk_strings(v, f);
            }
            body.iter().for_each(|e| walk_strings(e, f));
        }
        Expr::Do(es) | Expr::Builtin { args: es, .. } | Expr::Call { args: es, .. } => {
            es.iter().for_each(|e| walk_strings(e, f));
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

/// Per-function compilation context.
struct FnCtx<'a> {
    consts: &'a HashMap<String, i64>,
    fn_index: &'a HashMap<String, (u32, usize)>,
    literals: &'a Literals,
    /// (name, local-index) pairs; latest binding shadows earlier ones.
    scope: Vec<(String, u32)>,
    next_local: u32,
    arity: u32,
    out: Vec<Instruction<'a>>,
}

impl<'a> FnCtx<'a> {
    fn emit(&mut self, ins: Instruction<'a>) {
        self.out.push(ins);
    }
    fn resolve(&self, name: &str) -> Option<u32> {
        self.scope.iter().rev().find(|(n, _)| n == name).map(|(_, i)| *i)
    }
    fn alloc_local(&mut self) -> u32 {
        let i = self.next_local;
        self.next_local += 1;
        i
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

/// Compile an expression, leaving exactly one `i64` on the stack.
fn compile_expr(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    match expr {
        Expr::Int(i) => cg.emit(Instruction::I64Const(*i)),

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
            cg.emit(Instruction::If(BlockType::Result(ValType::I64)));
            compile_expr(cg, then)?;
            cg.emit(Instruction::Else);
            compile_expr(cg, els)?;
            cg.emit(Instruction::End);
        }

        Expr::Let { bindings, body } => {
            let saved = cg.scope.len();
            for (name, val) in bindings {
                compile_expr(cg, val)?;
                let idx = cg.alloc_local();
                cg.emit(Instruction::LocalSet(idx));
                cg.scope.push((name.clone(), idx));
            }
            compile_body(cg, body)?;
            cg.scope.truncate(saved); // bindings leave scope; local slots stay allocated
        }

        Expr::Do(exprs) => compile_body(cg, exprs)?,

        Expr::Builtin { op, args } => compile_builtin(cg, *op, args)?,

        Expr::Call { name, args } => {
            let (idx, arity) = cg
                .fn_index
                .get(name)
                .copied()
                .ok_or_else(|| CljError::Codegen(format!("call to unknown function `{name}`")))?;
            if args.len() != arity {
                return Err(CljError::Codegen(format!(
                    "`{name}` expects {arity} args, got {}",
                    args.len()
                )));
            }
            for a in args {
                compile_expr(cg, a)?;
            }
            cg.emit(Instruction::Call(idx));
        }
    }
    Ok(())
}

/// Compile `expr` and convert the resulting i64 to an i32 truthiness flag
/// (1 if non-zero, 0 if zero) suitable as a wasm `if`/`br_if` condition.
fn compile_truthy_i32(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    compile_expr(cg, expr)?;
    cg.emit(Instruction::I64Const(0));
    cg.emit(Instruction::I64Ne); // → i32: 1 if non-zero
    Ok(())
}

/// Compile `expr` to a normalised i64 boolean (1 if truthy, else 0).
fn compile_truthy_i64(cg: &mut FnCtx, expr: &Expr) -> Result<(), CljError> {
    compile_truthy_i32(cg, expr)?;
    cg.emit(Instruction::I64ExtendI32U);
    Ok(())
}

fn compile_builtin(cg: &mut FnCtx, op: Builtin, args: &[Expr]) -> Result<(), CljError> {
    match op {
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
        Builtin::Mod => binop(cg, args, Instruction::I64RemS),

        Builtin::Eq => cmp(cg, args, Instruction::I64Eq),
        Builtin::Lt => cmp(cg, args, Instruction::I64LtS),
        Builtin::Gt => cmp(cg, args, Instruction::I64GtS),
        Builtin::Le => cmp(cg, args, Instruction::I64LeS),
        Builtin::Ge => cmp(cg, args, Instruction::I64GeS),

        Builtin::Not => {
            compile_expr(cg, &args[0])?;
            cg.emit(Instruction::I64Eqz); // → i32: 1 if zero
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
        Builtin::And => compile_and(cg, args),
        Builtin::Or => compile_or(cg, args),

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
            cg.emit(Instruction::I32Load8U(MemArg {
                offset: 0,
                align: 0,
                memory_index: 0,
            }));
            cg.emit(Instruction::I64ExtendI32U);
            Ok(())
        }
    }
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

/// Comparison: two i64 operands → i32 result, extended back to i64 (1/0).
fn cmp(cg: &mut FnCtx, args: &[Expr], ins: Instruction<'static>) -> Result<(), CljError> {
    compile_expr(cg, &args[0])?;
    compile_expr(cg, &args[1])?;
    cg.emit(ins);
    cg.emit(Instruction::I64ExtendI32U);
    Ok(())
}

/// Short-circuit `and`, returning a normalised i64 boolean (0/1).
fn compile_and(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    if args.len() == 1 {
        return compile_truthy_i64(cg, &args[0]);
    }
    compile_truthy_i32(cg, &args[0])?;
    cg.emit(Instruction::If(BlockType::Result(ValType::I64)));
    compile_and(cg, &args[1..])?;
    cg.emit(Instruction::Else);
    cg.emit(Instruction::I64Const(0));
    cg.emit(Instruction::End);
    Ok(())
}

/// Short-circuit `or`, returning a normalised i64 boolean (0/1).
fn compile_or(cg: &mut FnCtx, args: &[Expr]) -> Result<(), CljError> {
    if args.len() == 1 {
        return compile_truthy_i64(cg, &args[0]);
    }
    compile_truthy_i32(cg, &args[0])?;
    cg.emit(Instruction::If(BlockType::Result(ValType::I64)));
    cg.emit(Instruction::I64Const(1));
    cg.emit(Instruction::Else);
    compile_or(cg, &args[1..])?;
    cg.emit(Instruction::End);
    Ok(())
}

// ---- compile-time constant evaluation (for `def`) ---------------------------

fn eval_consts(program: &Program) -> Result<HashMap<String, i64>, CljError> {
    let mut consts = HashMap::new();
    for d in &program.defs {
        let v = eval_const(&d.value, &consts)?;
        consts.insert(d.name.clone(), v);
    }
    Ok(consts)
}

fn eval_const(expr: &Expr, consts: &HashMap<String, i64>) -> Result<i64, CljError> {
    Ok(match expr {
        Expr::Int(i) => *i,
        Expr::Str(_) => {
            return Err(CljError::Codegen(
                "string literals are not allowed in a `def` initialiser".into(),
            ))
        }
        Expr::Var(name) => *consts
            .get(name)
            .ok_or_else(|| CljError::Codegen(format!("def references non-constant `{name}`")))?,
        Expr::If { cond, then, els } => {
            if eval_const(cond, consts)? != 0 {
                eval_const(then, consts)?
            } else {
                eval_const(els, consts)?
            }
        }
        Expr::Builtin { op, args } => {
            let v: Vec<i64> = args
                .iter()
                .map(|a| eval_const(a, consts))
                .collect::<Result<_, _>>()?;
            eval_const_builtin(*op, &v)?
        }
        Expr::Do(body) => eval_const(body.last().unwrap(), consts)?,
        Expr::Let { .. } => {
            return Err(CljError::Codegen(
                "`let` is not supported in a `def` initialiser".into(),
            ))
        }
        Expr::Call { name, .. } => {
            return Err(CljError::Codegen(format!(
                "`def` initialiser cannot call function `{name}` (must be a compile-time constant)"
            )))
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
        Builtin::Mod => v[0]
            .checked_rem(v[1])
            .ok_or_else(|| CljError::Codegen("rem by zero in const".into()))?,
        Builtin::Eq => b(v[0] == v[1]),
        Builtin::Lt => b(v[0] < v[1]),
        Builtin::Gt => b(v[0] > v[1]),
        Builtin::Le => b(v[0] <= v[1]),
        Builtin::Ge => b(v[0] >= v[1]),
        Builtin::Not => b(v[0] == 0),
        Builtin::And => b(v.iter().all(|x| *x != 0)),
        Builtin::Or => b(v.iter().any(|x| *x != 0)),
        Builtin::StrLen | Builtin::ByteAt => {
            return Err(CljError::Codegen(
                "string operations are not allowed in a `def` initialiser".into(),
            ))
        }
    })
}
