#include <stdint.h>
#include <stddef.h>

#define ELF_TEXT_VA 0x1e1000ULL
#define ELF_TEXT_OFFSET 4096ULL
#define ELF_DATA_OFFSET 65536ULL /* JUN-145: matches the packager data-offset (16 pages); user text room was 1 page */

extern int aiueos_kotoba_app_object(const uint8_t id[16],const uint8_t **data,uint64_t *length);
extern int aiueos_address_space_map_user_image(unsigned process,
  const uint8_t *text,uint64_t text_size,const uint8_t *data,uint64_t data_size,
  uint64_t data_va);
extern void *aiueos_address_space_user_data_backing(unsigned process);
extern uint64_t kotoba_aiueos_user_elf_valid(const uint8_t *image,uint64_t length);
extern uint64_t kotoba_aiueos_sha256(const uint8_t *,uint64_t,uint8_t *,uint8_t *,uint64_t);
extern uint64_t kotoba_aiueos_digest_equal(const uint8_t *,const uint8_t *,uint64_t);
static uint64_t loader_evidence;

static uint64_t load_u32(const uint8_t *value) {
  return (uint64_t)value[0] | ((uint64_t)value[1]<<8) |
    ((uint64_t)value[2]<<16) | ((uint64_t)value[3]<<24);
}

static int load_kotoba_process(unsigned process,const uint8_t *image,uint64_t size,
                               uint64_t *entry,uint64_t **result) {
  if (!image || !kotoba_aiueos_user_elf_valid(image,size)) return 0;
  /* Segment offsets come from the program headers, not from the pinned
     constants (JUN-145, measured 2026-10-20): every shipped user ELF is
     catalog-signed, so a layout pin would orphan them the moment the
     packager grew the text room. The phdrs carry the truth for both the
     old 8 KiB-data artifacts and the new 64 KiB ones. */
  uint64_t phoff=load_u32(image+32)|(load_u32(image+36)<<32);
  uint64_t phentsize=load_u32(image+54)&0xffff;
  uint64_t phnum=(load_u32(image+54)>>16)&0xffff;
  uint64_t text_off=0,text_size=0,data_off=0,data_va=0,entry_va=0;
  if (phentsize<56 || phoff+phnum*phentsize>size) return 0;
  for (uint64_t i=0;i<phnum;i++) {
    const uint8_t *ph=image+phoff+i*phentsize;
    uint32_t flags=load_u32(ph+4);
    uint64_t off=load_u32(ph+8)|(load_u32(ph+12)<<32);
    uint64_t vaddr=load_u32(ph+16)|(load_u32(ph+20)<<32);
    uint64_t filesz=load_u32(ph+32)|(load_u32(ph+36)<<32);
    if (flags==0x5 && filesz) { text_off=off; text_size=filesz; entry_va=vaddr; }
    if (flags==0x6) { data_off=off; data_va=vaddr; }
  }
  if (!text_size || !data_off || !data_va || text_off+text_size>size) return 0;
  /* Kind 3 now receives the data segment's p_vaddr, not its byte count
     (JUN-145 ③): the mapping plan maps the page the program header names, so
     the old 8 KiB-data layout maps 0x1e2000 and the current packager's 64 KiB
     one maps 0x1f0000 out of the same call. */
  if (!aiueos_address_space_map_user_image(process,image+text_off,text_size,
        image+data_off,88,data_va)) return 0;
  *entry=entry_va?entry_va:ELF_TEXT_VA;
  *result=aiueos_address_space_user_data_backing(process);
  loader_evidence=*result!=0;
  return (int)loader_evidence;
}
int aiueos_load_object_store_kotoba_process(unsigned process,const uint8_t app_id[16],uint64_t *entry,
                                         uint64_t **result) {
  const uint8_t *image=0; uint64_t size=0;
  if (!aiueos_kotoba_app_object(app_id,&image,&size)) return 0;
  return load_kotoba_process(process,image,size,entry,result);
}
#ifdef AIUEOS_PLC_RT_SMOKE
extern const uint8_t aiueos_plc_elf_start[],aiueos_plc_elf_end[];
extern const uint8_t aiueos_plc_elf_sha256[32],aiueos_plc_receipt_sha256[32];
extern const uint8_t aiueos_plc_signature[64],aiueos_plc_public_key[64];
extern uint64_t kotoba_aiueos_ecdsa_p256_sha256_verify(
  const uint8_t *,const uint8_t *,const uint8_t *,uint8_t *,uint64_t);
static uint8_t plc_signature_workspace[2048];
volatile uint64_t aiueos_plc_loader_stage;
int aiueos_load_embedded_plc_process(unsigned process,uint64_t *entry,uint64_t **result) {
  uint8_t actual[32],workspace[512],nonzero=0;
  uint64_t size=(uint64_t)(aiueos_plc_elf_end-aiueos_plc_elf_start);
  aiueos_plc_loader_stage=1;
  if (!size || size>98304) return 0;
  if (!kotoba_aiueos_sha256(aiueos_plc_elf_start,size,actual,workspace,sizeof(workspace))) return 0;
  aiueos_plc_loader_stage=2;
  if (!kotoba_aiueos_digest_equal(actual,aiueos_plc_elf_sha256,32)) return 0;
  aiueos_plc_loader_stage=3;
  uint8_t invalid_signature[64];
  for (unsigned i=0;i<64;i++) invalid_signature[i]=aiueos_plc_signature[i];
  invalid_signature[0]^=1;
  if (kotoba_aiueos_ecdsa_p256_sha256_verify(invalid_signature,actual,
      aiueos_plc_public_key,plc_signature_workspace,sizeof(plc_signature_workspace))) return 0;
  if (!kotoba_aiueos_ecdsa_p256_sha256_verify(aiueos_plc_signature,actual,
      aiueos_plc_public_key,plc_signature_workspace,sizeof(plc_signature_workspace))) return 0;
  aiueos_plc_loader_stage=4;
  for (unsigned i=0;i<32;i++) nonzero|=aiueos_plc_receipt_sha256[i];
  if (!nonzero) return 0;
  aiueos_plc_loader_stage=5;
  if (!kotoba_aiueos_user_elf_valid(aiueos_plc_elf_start,size)) return 0;
  aiueos_plc_loader_stage=6;
  uint64_t text_size=load_u32(aiueos_plc_elf_start+96);
  /* p_vaddr of the data phdr at the position the PLC validator admits
     (phoff 64 + phentsize 56): the mapping plan is given the address the
     program header names, never a byte count. */
  uint64_t data_va=load_u32(aiueos_plc_elf_start+136)|
    (load_u32(aiueos_plc_elf_start+140)<<32);
  if (!data_va) return 0;
  if (!aiueos_address_space_map_user_image(process,
      aiueos_plc_elf_start+ELF_TEXT_OFFSET,text_size,
      aiueos_plc_elf_start+ELF_DATA_OFFSET,88,data_va)) return 0;
  aiueos_plc_loader_stage=7;
  *entry=ELF_TEXT_VA;
  *result=aiueos_address_space_user_data_backing(process);
  return *result!=0;
}
int aiueos_reset_embedded_plc_context(uint64_t *result,uint64_t runtime_handle) {
  if (!result || !runtime_handle) return 0;
  for (unsigned i=0;i<88;i++)
    ((uint8_t *)result)[i]=aiueos_plc_elf_start[ELF_DATA_OFFSET+i];
  result[10]=runtime_handle;
  return 1;
}
#endif
int aiueos_kotoba_process_loader_evidence_ready(void) { return (int)loader_evidence; }
