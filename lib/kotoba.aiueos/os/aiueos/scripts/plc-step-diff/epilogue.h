/* Entry points over one copy of the scan-cycle core, for scripts/plc-step-diff: reset, release, a capability call, the
   two test hooks plc_failure_vectors uses (physical outputs, budget_end) and a snapshot of the whole runtime struct. */
void PFX(reset)(void) { plc_reset(); }
int PFX(release)(uint64_t now, int32_t in0, int32_t in1) { plc.physical_input[0]=in0; plc.physical_input[1]=in1; return plc_release(now); }
uint64_t PFX(call)(uint64_t c, uint64_t a, uint64_t now) { return plc_call(c, a, now); }
void PFX(poke)(uint64_t budget_end, int32_t out0, int32_t safe0, uint64_t next_release) {
  plc.budget_end=budget_end; plc.physical_output[0]=out0; plc.safe_output[0]=safe0; plc.next_release=next_release; }
void PFX(extend_budget)(uint64_t extra) { plc.budget_end=plc.deadline+extra; }
void PFX(snap)(uint64_t s[16]) {
  for (unsigned i=0;i<2;i++) { s[i]=(uint32_t)plc.physical_input[i]; s[2+i]=(uint32_t)plc.input_image[i];
    s[4+i]=(uint32_t)plc.shadow_output[i]; s[6+i]=(uint32_t)plc.physical_output[i]; s[8+i]=(uint32_t)plc.safe_output[i]; }
  s[10]=plc.next_release; s[11]=plc.release; s[12]=plc.deadline; s[13]=plc.budget_end;
  s[14]=plc.staged; s[15]=plc.active|(uint64_t)plc.watchdog<<8|(uint64_t)plc.fault_latched<<16|(uint64_t)plc.fault<<24;
}
