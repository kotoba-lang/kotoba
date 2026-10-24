(ns policy.ports
  "Host-injected ports for evaluating a policy model. policy-clj defines the
  protocols; the host supplies concrete implementations (call an attribute store,
  an LDAP directory, a JWT claims resolver, …). The decision engine in
  `policy.execute` is pure over these — no I/O of its own.")

(defprotocol IAttribute
  "Resolve an attribute path string (e.g. \"user.role\") against a request map,
  returning the attribute value or nil. The host controls the source: it may be
  a claims map from a JWT, a row from a user table, or a remote attribute store."
  (resolve [this attr-path request] "attr-path-string + request-map → value"))
