/* @ts-self-types="./kami_isaac_sim_wasm.d.cts" */

/**
 * JS-callable handle around an `IsaacWorld` scene of articulations.
 */
class IsaacWorldHandle {
    __destroy_into_raw() {
        const ptr = this.__wbg_ptr;
        this.__wbg_ptr = 0;
        IsaacWorldHandleFinalization.unregister(this);
        return ptr;
    }
    free() {
        const ptr = this.__destroy_into_raw();
        wasm.__wbg_isaacworldhandle_free(ptr, 0);
    }
    /**
     * `world.scene.add(Articulation(urdf))` — parses `urdf_text` and
     * registers it. Returns an opaque handle index for the other methods.
     * Panics on malformed URDF or an unsupported topology, matching the
     * `kami-cartpole-wasm` precedent's `.expect(...)` style; graceful
     * `Result`-based error propagation to JS is a follow-up.
     * @param {string} urdf_text
     * @returns {number}
     */
    add_articulation_from_urdf(urdf_text) {
        const ptr0 = passStringToWasm0(urdf_text, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.isaacworldhandle_add_articulation_from_urdf(this.__wbg_ptr, ptr0, len0);
        return ret >>> 0;
    }
    /**
     * `controller.apply_action(ArticulationAction(joint_efforts=targets))`
     * — direct feedforward effort, clamped by `set_max_efforts`.
     * @param {number} handle
     * @param {Float32Array} targets
     */
    apply_effort_action(handle, targets) {
        const ptr0 = passArrayF32ToWasm0(targets, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_apply_effort_action(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `controller.apply_action(ArticulationAction(joint_positions=targets))`
     * — PD-tracked position targets, using the gains from `set_gains`.
     * @param {number} handle
     * @param {Float32Array} targets
     */
    apply_position_action(handle, targets) {
        const ptr0 = passArrayF32ToWasm0(targets, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_apply_position_action(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `world.current_time`.
     * @returns {number}
     */
    current_time() {
        const ret = wasm.isaacworldhandle_current_time(this.__wbg_ptr);
        return ret;
    }
    /**
     * `world.current_time_step_index`.
     * @returns {number}
     */
    current_time_step_index() {
        const ret = wasm.isaacworldhandle_current_time_step_index(this.__wbg_ptr);
        return ret >>> 0;
    }
    /**
     * `articulation.dof_names` (property).
     * @param {number} handle
     * @returns {string[]}
     */
    dof_names(handle) {
        const ret = wasm.isaacworldhandle_dof_names(this.__wbg_ptr, handle);
        var v1 = getArrayJsValueFromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * `articulation.get_joint_positions()` → `[n_dof]`.
     * @param {number} handle
     * @returns {Float32Array}
     */
    get_joint_positions(handle) {
        const ret = wasm.isaacworldhandle_get_joint_positions(this.__wbg_ptr, handle);
        var v1 = getArrayF32FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * `articulation.get_joint_velocities()` → `[n_dof]`.
     * @param {number} handle
     * @returns {Float32Array}
     */
    get_joint_velocities(handle) {
        const ret = wasm.isaacworldhandle_get_joint_velocities(this.__wbg_ptr, handle);
        var v1 = getArrayF32FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v1;
    }
    /**
     * `world.get_physics_dt()`.
     * @returns {number}
     */
    get_physics_dt() {
        const ret = wasm.isaacworldhandle_get_physics_dt(this.__wbg_ptr);
        return ret;
    }
    /**
     * `RigidPrimView.get_world_poses(link)` → `[px,py,pz, qw,qx,qy,qz]` (7
     * floats), or an empty array if the link/handle is unknown.
     * @param {number} handle
     * @param {string} link_name
     * @returns {Float32Array}
     */
    get_world_pose(handle, link_name) {
        const ptr0 = passStringToWasm0(link_name, wasm.__wbindgen_malloc, wasm.__wbindgen_realloc);
        const len0 = WASM_VECTOR_LEN;
        const ret = wasm.isaacworldhandle_get_world_pose(this.__wbg_ptr, handle, ptr0, len0);
        var v2 = getArrayF32FromWasm0(ret[0], ret[1]).slice();
        wasm.__wbindgen_free(ret[0], ret[1] * 4, 4);
        return v2;
    }
    /**
     * `new IsaacWorldHandle(physicsDt)` ~ `isaacsim.core.api.World(physics_dt=...)`.
     * @param {number} physics_dt
     */
    constructor(physics_dt) {
        const ret = wasm.isaacworldhandle_new(physics_dt);
        this.__wbg_ptr = ret;
        IsaacWorldHandleFinalization.register(this, this.__wbg_ptr, this);
        return this;
    }
    /**
     * `articulation.num_dof` (property).
     * @param {number} handle
     * @returns {number}
     */
    num_dof(handle) {
        const ret = wasm.isaacworldhandle_num_dof(this.__wbg_ptr, handle);
        return ret >>> 0;
    }
    /**
     * `world.reset()` — zero all registered articulations' joint state.
     */
    reset() {
        wasm.isaacworldhandle_reset(this.__wbg_ptr);
    }
    /**
     * `controller.set_gains(kps, kds)`.
     * @param {number} handle
     * @param {Float32Array} kps
     * @param {Float32Array} kds
     */
    set_gains(handle, kps, kds) {
        const ptr0 = passArrayF32ToWasm0(kps, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        const ptr1 = passArrayF32ToWasm0(kds, wasm.__wbindgen_malloc);
        const len1 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_set_gains(this.__wbg_ptr, handle, ptr0, len0, ptr1, len1);
    }
    /**
     * `articulation.set_joint_efforts(efforts)`.
     * @param {number} handle
     * @param {Float32Array} efforts
     */
    set_joint_efforts(handle, efforts) {
        const ptr0 = passArrayF32ToWasm0(efforts, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_set_joint_efforts(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `articulation.set_joint_positions(positions)` — seed/teleport.
     * @param {number} handle
     * @param {Float32Array} positions
     */
    set_joint_positions(handle, positions) {
        const ptr0 = passArrayF32ToWasm0(positions, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_set_joint_positions(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `articulation.set_joint_velocities(velocities)`.
     * @param {number} handle
     * @param {Float32Array} velocities
     */
    set_joint_velocities(handle, velocities) {
        const ptr0 = passArrayF32ToWasm0(velocities, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_set_joint_velocities(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `controller.set_max_efforts(max_efforts)`.
     * @param {number} handle
     * @param {Float32Array} max_efforts
     */
    set_max_efforts(handle, max_efforts) {
        const ptr0 = passArrayF32ToWasm0(max_efforts, wasm.__wbindgen_malloc);
        const len0 = WASM_VECTOR_LEN;
        wasm.isaacworldhandle_set_max_efforts(this.__wbg_ptr, handle, ptr0, len0);
    }
    /**
     * `world.step(render=False)` — advance physics by one `physics_dt`.
     */
    step() {
        wasm.isaacworldhandle_step(this.__wbg_ptr);
    }
}
if (Symbol.dispose) IsaacWorldHandle.prototype[Symbol.dispose] = IsaacWorldHandle.prototype.free;
exports.IsaacWorldHandle = IsaacWorldHandle;

/**
 * `kamiIsaacSimWasmVersion()` — version banner for HUD/audit strings.
 * @returns {string}
 */
function kamiIsaacSimWasmVersion() {
    let deferred1_0;
    let deferred1_1;
    try {
        const ret = wasm.kamiIsaacSimWasmVersion();
        deferred1_0 = ret[0];
        deferred1_1 = ret[1];
        return getStringFromWasm0(ret[0], ret[1]);
    } finally {
        wasm.__wbindgen_free(deferred1_0, deferred1_1, 1);
    }
}
exports.kamiIsaacSimWasmVersion = kamiIsaacSimWasmVersion;
function __wbg_get_imports() {
    const import0 = {
        __proto__: null,
        __wbg___wbindgen_throw_344f42d3211c4765: function(arg0, arg1) {
            throw new Error(getStringFromWasm0(arg0, arg1));
        },
        __wbindgen_cast_0000000000000001: function(arg0, arg1) {
            // Cast intrinsic for `Ref(String) -> Externref`.
            const ret = getStringFromWasm0(arg0, arg1);
            return ret;
        },
        __wbindgen_init_externref_table: function() {
            const table = wasm.__wbindgen_externrefs;
            const offset = table.grow(4);
            table.set(0, undefined);
            table.set(offset + 0, undefined);
            table.set(offset + 1, null);
            table.set(offset + 2, true);
            table.set(offset + 3, false);
        },
    };
    return {
        __proto__: null,
        "./kami_isaac_sim_wasm_bg.js": import0,
    };
}

const IsaacWorldHandleFinalization = (typeof FinalizationRegistry === 'undefined')
    ? { register: () => {}, unregister: () => {} }
    : new FinalizationRegistry(ptr => wasm.__wbg_isaacworldhandle_free(ptr, 1));

function getArrayF32FromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    return getFloat32ArrayMemory0().subarray(ptr / 4, ptr / 4 + len);
}

function getArrayJsValueFromWasm0(ptr, len) {
    ptr = ptr >>> 0;
    const mem = getDataViewMemory0();
    const result = [];
    for (let i = ptr; i < ptr + 4 * len; i += 4) {
        result.push(wasm.__wbindgen_externrefs.get(mem.getUint32(i, true)));
    }
    wasm.__externref_drop_slice(ptr, len);
    return result;
}

let cachedDataViewMemory0 = null;
function getDataViewMemory0() {
    if (cachedDataViewMemory0 === null || cachedDataViewMemory0.buffer.detached === true || (cachedDataViewMemory0.buffer.detached === undefined && cachedDataViewMemory0.buffer !== wasm.memory.buffer)) {
        cachedDataViewMemory0 = new DataView(wasm.memory.buffer);
    }
    return cachedDataViewMemory0;
}

let cachedFloat32ArrayMemory0 = null;
function getFloat32ArrayMemory0() {
    if (cachedFloat32ArrayMemory0 === null || cachedFloat32ArrayMemory0.byteLength === 0) {
        cachedFloat32ArrayMemory0 = new Float32Array(wasm.memory.buffer);
    }
    return cachedFloat32ArrayMemory0;
}

function getStringFromWasm0(ptr, len) {
    return decodeText(ptr >>> 0, len);
}

let cachedUint8ArrayMemory0 = null;
function getUint8ArrayMemory0() {
    if (cachedUint8ArrayMemory0 === null || cachedUint8ArrayMemory0.byteLength === 0) {
        cachedUint8ArrayMemory0 = new Uint8Array(wasm.memory.buffer);
    }
    return cachedUint8ArrayMemory0;
}

function passArrayF32ToWasm0(arg, malloc) {
    const ptr = malloc(arg.length * 4, 4) >>> 0;
    getFloat32ArrayMemory0().set(arg, ptr / 4);
    WASM_VECTOR_LEN = arg.length;
    return ptr;
}

function passStringToWasm0(arg, malloc, realloc) {
    if (realloc === undefined) {
        const buf = cachedTextEncoder.encode(arg);
        const ptr = malloc(buf.length, 1) >>> 0;
        getUint8ArrayMemory0().subarray(ptr, ptr + buf.length).set(buf);
        WASM_VECTOR_LEN = buf.length;
        return ptr;
    }

    let len = arg.length;
    let ptr = malloc(len, 1) >>> 0;

    const mem = getUint8ArrayMemory0();

    let offset = 0;

    for (; offset < len; offset++) {
        const code = arg.charCodeAt(offset);
        if (code > 0x7F) break;
        mem[ptr + offset] = code;
    }
    if (offset !== len) {
        if (offset !== 0) {
            arg = arg.slice(offset);
        }
        ptr = realloc(ptr, len, len = offset + arg.length * 3, 1) >>> 0;
        const view = getUint8ArrayMemory0().subarray(ptr + offset, ptr + len);
        const ret = cachedTextEncoder.encodeInto(arg, view);

        offset += ret.written;
        ptr = realloc(ptr, len, offset, 1) >>> 0;
    }

    WASM_VECTOR_LEN = offset;
    return ptr;
}

let cachedTextDecoder = new TextDecoder('utf-8', { ignoreBOM: true, fatal: true });
cachedTextDecoder.decode();
function decodeText(ptr, len) {
    return cachedTextDecoder.decode(getUint8ArrayMemory0().subarray(ptr, ptr + len));
}

const cachedTextEncoder = new TextEncoder();

if (!('encodeInto' in cachedTextEncoder)) {
    cachedTextEncoder.encodeInto = function (arg, view) {
        const buf = cachedTextEncoder.encode(arg);
        view.set(buf);
        return {
            read: arg.length,
            written: buf.length
        };
    };
}

let WASM_VECTOR_LEN = 0;

const wasmPath = `${__dirname}/kami_isaac_sim_wasm_bg.wasm`;
const wasmBytes = require('fs').readFileSync(wasmPath);
const wasmModule = new WebAssembly.Module(wasmBytes);
let wasmInstance = new WebAssembly.Instance(wasmModule, __wbg_get_imports());
let wasm = wasmInstance.exports;
wasm.__wbindgen_start();
