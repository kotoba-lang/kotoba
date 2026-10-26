#include <stdint.h>

#define EFIAPI __attribute__((ms_abi))
#define EFI_SUCCESS 0
#define EFI_VARIABLE_NON_VOLATILE 1U
#define EFI_VARIABLE_BOOTSERVICE_ACCESS 2U
#define EFI_VARIABLE_RUNTIME_ACCESS 4U

typedef uint64_t efi_status;
typedef uint16_t char16;

struct efi_guid { uint32_t a; uint16_t b, c; uint8_t d[8]; };
struct efi_table_header {
  uint64_t signature;
  uint32_t revision, header_size, crc32, reserved;
};
struct efi_time {
  uint16_t year;
  uint8_t month, day, hour, minute, second, pad1;
  uint32_t nanosecond;
  int16_t timezone;
  uint8_t daylight, pad2;
};
typedef efi_status(EFIAPI *efi_get_time)(struct efi_time *, void *);
typedef efi_status(EFIAPI *efi_get_variable)(const char16 *, const struct efi_guid *,
                                             uint32_t *, uint64_t *, void *);
typedef efi_status(EFIAPI *efi_set_variable)(const char16 *, const struct efi_guid *,
                                             uint32_t, uint64_t, void *);
typedef void(EFIAPI *efi_reset_system)(uint32_t, efi_status, uint64_t, void *);
struct efi_runtime_services {
  struct efi_table_header header;
  efi_get_time get_time;
  void *set_time, *get_wakeup_time, *set_wakeup_time;
  void *set_virtual_address_map, *convert_pointer;
  efi_get_variable get_variable;
  void *get_next_variable_name;
  efi_set_variable set_variable;
  void *get_next_high_monotonic_count;
  efi_reset_system reset_system;
};

struct aiueos_qualification_record {
  uint32_t magic;
  uint16_t version, state;
  uint32_t code, reserved;
};

static const struct efi_guid qualification_guid =
  {0x73953a72,0x6627,0x4b62,{0x9a,0x9c,0x10,0x38,0xd9,0x20,0x9a,0x16}};
static const char16 qualification_name[] = u"AIUEOSQualificationResult";
static const char16 device_p256_key_name[] = u"AIUEOSDeviceP256Key";
static struct efi_runtime_services *qualification_runtime;
/* Read by qualification_entry.S before any C prologue executes under the
   final split-W^X root.  Keep this symbol externally visible to that bounded
   assembly trampoline; it is not part of the general kernel API. */
uint64_t qualification_firmware_cr3;

void aiueos_qualification_runtime_initialize(void *runtime_services,
                                              uint64_t firmware_cr3) {
  qualification_runtime = runtime_services;
  qualification_firmware_cr3 = firmware_cr3;
}

/* Paging may normalize a firmware PCID before clearing CR4.PCIDE.  Keep the
   recorder's bounded hand-back root in lockstep so later progress calls never
   attempt to load a stale nonzero PCID while PCIDE is disabled. */
void aiueos_qualification_runtime_set_firmware_cr3(uint64_t firmware_cr3) {
  qualification_firmware_cr3 = firmware_cr3;
}

int aiueos_device_p256_key_load_firmware(uint8_t key[32]) {
  struct efi_runtime_services *runtime = qualification_runtime;
  if (!runtime || !qualification_firmware_cr3 || !runtime->get_variable || !key)
    return 0;
  uint32_t attributes = 0;
  uint64_t bytes = 32;
  efi_status status = runtime->get_variable(
      device_p256_key_name, &qualification_guid, &attributes, &bytes, key);
  return status == EFI_SUCCESS && bytes == 32 &&
    (attributes & (EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_RUNTIME_ACCESS)) ==
      (EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_RUNTIME_ACCESS);
}

int aiueos_device_p256_key_save_firmware(const uint8_t key[32]) {
  struct efi_runtime_services *runtime = qualification_runtime;
  if (!runtime || !qualification_firmware_cr3 || !runtime->set_variable || !key)
    return 0;
  return runtime->set_variable(
           device_p256_key_name, &qualification_guid,
           EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS |
             EFI_VARIABLE_RUNTIME_ACCESS,
           32, (void *)key) == EFI_SUCCESS;
}

/* Keep the last entered physical-qualification stage across a hang or manual
   power cycle. This has the same 16-byte NVRAM-only boundary as finalize, but
   deliberately does not reset the machine or touch a block device.  The
   assembly entry has already restored the firmware CR3 before calling here. */
int aiueos_qualification_progress_firmware(uint32_t code) {
  struct efi_runtime_services *runtime = qualification_runtime;
  if (!runtime || !qualification_firmware_cr3 || !runtime->set_variable) return 0;
  struct aiueos_qualification_record record = {
    0x514b3241U, 2, 0, code, 0
  };
  efi_status status = runtime->set_variable(
      qualification_name, &qualification_guid,
      EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS |
        EFI_VARIABLE_RUNTIME_ACCESS,
      sizeof(record), &record);
  return status == EFI_SUCCESS;
}

/* Persist only a bounded result code in firmware NVRAM.  Qualification builds
   warm-reset into the one-shot BootNext entry installed by the USB probe;
   persistent native builds return to the kernel so the live node can keep
   renewing its lease.  Neither path reaches a block driver or an
   internal-disk path.  As above, the assembly entry restores the firmware CR3
   before any C code executes. */
int aiueos_qualification_finalize_firmware(uint16_t state, uint32_t code) {
  struct efi_runtime_services *runtime = qualification_runtime;
  if (!runtime || !qualification_firmware_cr3 || !runtime->set_variable)
    return 0;
#ifndef AIUEOS_PERSISTENT_BOOT
  if (!runtime->reset_system) return 0;
#endif

  struct aiueos_qualification_record record = {
    0x514b3241U, 2, state, code, 0
  };
  efi_status status = runtime->set_variable(
      qualification_name, &qualification_guid,
      EFI_VARIABLE_NON_VOLATILE | EFI_VARIABLE_BOOTSERVICE_ACCESS |
        EFI_VARIABLE_RUNTIME_ACCESS,
      sizeof(record), &record);
  if (status != EFI_SUCCESS) return 0;
#ifdef AIUEOS_PERSISTENT_BOOT
  return 1;
#else
  runtime->reset_system(1, EFI_SUCCESS, 0, 0);
  return 0;
#endif
}

/* Execute a cold firmware reset only after the worker has received an HTTP
   2xx response to its signed control acknowledgement.  The assembly entry
   restores the firmware page-table root before calling Runtime Services.
   Boot order remains firmware-owned; on the K16 it is already PXE-first. */
int aiueos_qualification_reboot_firmware(void) {
  struct efi_runtime_services *runtime = qualification_runtime;
  if (!runtime || !qualification_firmware_cr3 || !runtime->reset_system)
    return 0;
  runtime->reset_system(0, EFI_SUCCESS, 0, 0);
  return 0;
}
