import { createWorkerdHandler } from "./portable-effect-host.mjs";
import { instantiateKotoba } from "./generated/portable-effect.mjs";

const kotoba = instantiateKotoba({});
const policy = Object.freeze({
  ndlScopeAdmitted: kotoba["ndl-scope-admitted"],
  ndlLimitsAdmitted: kotoba["ndl-limits-admitted"]
});

export default createWorkerdHandler({ policy });
