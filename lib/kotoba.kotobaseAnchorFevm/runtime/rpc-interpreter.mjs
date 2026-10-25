// Compatibility facade. New code imports runtime/evm-interpreter.mjs and an
// explicit network profile; Filecoin is no longer a core runtime dependency.
export {ANCHOR_ABI, EvmRpcInterpreter, EvmRpcInterpreter as FevmRpcInterpreter,
  evmInterpreterFromEnv, privateAnchorMaterial} from "./evm-interpreter.mjs";
export {FILECOIN_CALIBRATION as CALIBRATION} from "../profiles/filecoin-calibration.mjs";

import {evmInterpreterFromEnv} from "./evm-interpreter.mjs";
import {FILECOIN_CALIBRATION} from "../profiles/filecoin-calibration.mjs";

export const calibrationInterpreterFromEnv = (env = process.env) =>
  evmInterpreterFromEnv(FILECOIN_CALIBRATION, env);
