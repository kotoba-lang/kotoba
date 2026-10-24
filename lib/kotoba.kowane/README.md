# kowane (声音)

A linear-prediction vocoder for 8 kHz speech at **2400 and 1200 bit/s** —
voice that fits LoRa. 10 reflection coefficients + pitch/voicing + gain in 48
bits per frame (20 ms or 40 ms); lattice synthesis with pulse/noise
excitation; frame concealment.

Written from the textbook LPC method in pure kotoba. **Not** bit-compatible
with LPC-10, MELP or Codec2, and intelligible rather than natural, as every
vocoder at these rates is.

```clojure
(require '[kowane.lpc :as lpc])
(lpc/encode :lpc-2400 samples)            ; 6 bytes per 160 samples
(second (lpc/decode :lpc-2400 bytes))     ; samples
```

```sh
npm test
```
