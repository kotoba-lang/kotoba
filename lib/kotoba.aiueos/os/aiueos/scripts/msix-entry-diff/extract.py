# The MSI-X programming of setup_rng_msix and setup_blk_msix in a kernel/pci.c, from the line after the table entry
# pointer to the line before the MSI-X enable, as PREFIX_rng(cfg, entry) and PREFIX_blk(cfg, entry, address, data)
# answering 1 when the C carried on. Shared by old.c's provenance (main 4008b9d7) and gen-new.py. JUN-598.
def extract(src, prefix):
    out = []
    for name, sig in (("setup_rng_msix", "volatile struct virtio_common_cfg *cfg, struct msix_entry *entry"),
                      ("setup_blk_msix", "volatile struct virtio_common_cfg *cfg, struct msix_entry *entry, "
                                         "uint32_t message_address, uint32_t message_data")):
        a = src.index("static int %s(" % name)
        lo = src.index("  struct msix_entry *entry = (void *)(uintptr_t)(table_base + table_offset);\n", a)
        lo = src.index("\n", lo) + 1
        if name == "setup_blk_msix":
            lo = src.index("&message_address,&message_data)) return 0;\n", lo)   # past the VT-d remap
            lo = src.index("\n", lo) + 1
        hi = src.index("  config_write(b,d,f,pointer,header | (1U << 31));", lo)
        out.append("int %s_%s(%s) {\n%s  return 1;\n}\n" % (prefix, name.split("_")[1], sig, src[lo:hi]))
    return "".join(out)
