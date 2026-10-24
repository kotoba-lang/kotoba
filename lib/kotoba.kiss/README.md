# kiss

KISS framing for talking to a radio modem over serial / USB / BLE UART, with
a streaming decoder that survives frames split across reads and line noise;
radio-parameter commands for a LoRa modem (this project's own command set on
types 8–14 — no claim of compatibility with other firmware); and
`kiss.airtime`, a transmit governor for 920 MHz licence-free operation in
Japan (per-transmission limit, pause, hourly budget — parameters to confirm
against ARIB STD-T108 for your channel configuration).

```sh
npm test
```
