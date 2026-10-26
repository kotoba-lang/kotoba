(ns tls.harness
  "The provider the tests run against: the shipped `tls.provider.jvm`, adapted
  to byte vectors by `tls.provider.vectors`.

  There used to be a stand-in here, written so the protocol layers could be
  verified before the real provider landed. It is deleted. A stand-in and the
  shipped provider agreeing is exactly the sort of thing that gets assumed
  rather than checked, and the cheapest way not to assume it is to have only
  one provider."
  (:require [tls.provider.jvm :as jvm]
            [tls.provider.vectors :as pv]
            [tls.result :as r]))

(def array-provider
  "The canonical, byte-array-shaped provider -- what `tls.cert` and
   `tls.provider` tests take."
  (delay (jvm/provider)))

(def provider
  "The same provider, speaking byte vectors -- what the protocol layer takes.

   `pv/adapt` refuses a provider that fails `tls.provider/validate` or any of
   its known answers (FIPS 180-4, RFC 4231, RFC 7748), so a test suite cannot
   run against a broken one and report a pass."
  (delay (let [res (pv/adapt @array-provider)]
           (if (r/ok? res)
             (r/val res)
             (throw (ex-info "tls.harness: the shipped provider was refused"
                             {:error (r/err res)}))))))
