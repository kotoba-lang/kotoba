# com-intel-xe-driver

Kotoba-language driver core for Intel Xe2/Battlemage PCI device `8086:e223`
(Intel Arc Pro B70). It is a clean-room, fail-closed admission and bring-up
contract for AIUEOS and is not affiliated with or endorsed by Intel.

The current vertical slice is intentionally narrow and executable:

- admits only the observed B70 identity and VGA class;
- requires BAR0 >= 16 MiB and physical Resizable BAR2 >= 32 GiB;
- requires memory decoding, bus mastering, IOMMU, DMA, and IRQ grants;
- returns a four-step bounded bring-up plan (BAR0, BAR2, DMA, IRQ);
- grades the observed PCIe 2.5 GT/s x1 link as performance-degraded without
  falsely treating a working compute device as absent;
- contains positive and mutation/rejection vectors in Kotoba `main`.

It does **not** yet replace Linux's `xe` kernel driver, submit GPU command
buffers, load GuC firmware, manage virtual memory, or execute shaders. Those
mechanisms must be added behind the existing atomic authority packages:
`capability-pci-config`, `capability-mmio-map`, `capability-dma-map`, and
`capability-irq-subscribe`. Generic GPU pipeline IR remains owned by
`kotoba-lang/gpu`.

## Verify

```sh
amu check src/com/intel/xe_driver.kotoba
amu test src/com/intel/xe_driver.kotoba --json
```

The hardware acceptance vector comes from the installed Murakumo B70 node:
vendor/device `8086:e223`, class `0300`, BAR0 16 MiB, BAR2 32 GiB, IOMMU group
14, ATS enabled, MSI enabled, Linux `xe` bound.

Primary references: Intel's official
[Xe driver GPU table](https://dgpu-docs.intel.com/overview/supported-hardware/xe-driver-gpus.html)
and Linux's upstream [`xe_pci.c`](https://github.com/torvalds/linux/blob/master/drivers/gpu/drm/xe/xe_pci.c).

## License

Apache-2.0. See [LICENSE](LICENSE).
