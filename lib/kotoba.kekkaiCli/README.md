# kekkai-cli

**One command line for the kekkai overlay**: make keys, publish a signed
netmap, run a node, and `ssh` across the mesh.

```bash
kekkai keygen authority                  # the control plane's signing identity
kekkai keygen --node-id judah            # a node's Noise identity
kekkai netmap publish --plane plane.edn --authority authority.edn
kekkai desired publish --input desired.edn --authority authority.edn \
  --roots ssh://asher/var/lib/kekkai,ssh://judah/var/lib/kekkai
kekkai relay --config relay.edn --tailnet fleet --version 1
kekkai up --config node-judah.edn
kekkai ssh judah                         # ← the point
```

## Why this repository exists at all

The engine has two halves and neither should contain this.
[`kekkai`](https://github.com/kotoba-lang/kekkai) is the control plane: it
admits devices and **publishes** signed netmaps.
[`kekkai-node`](https://github.com/kotoba-lang/kekkai-node) is the data plane:
it **consumes** them. Putting `netmap publish` into the node would put the
signing key in the data plane and invert the relationship the charter is built
on — the node is not supposed to be able to author its own reachability.

So the CLI depends on both and neither depends on it.

It runs entirely on nbb. That was not obvious: `kekkai.envelope` (the JVM
signer) uses `java.security`, which would have forced a JVM subprocess for the
one command that matters most. Measured first: `kekkai.netmap/publish` is pure
`.cljc` and its output is **byte-identical** under Clojure and ClojureScript,
and Ed25519 is deterministic — so `kekkai.cli.sign` reproduces the JVM
publisher's bytes exactly. That equality is pinned as a test against `kekkai`'s
committed fixture rather than assumed, because it depends on maps of eight keys
or fewer printing in insertion order on both runtimes. A nine-key map would
break it silently, and the test is what makes that break loud.

## `kekkai ssh`

```
kekkai ssh <node> [--user U] [--port N] [ssh args…]
```

Starts an agent, waits for the overlay session, opens an ephemeral forwarder on
127.0.0.1, and hands the port to the **real** `ssh` with inherited stdio — so
keys, agents, `~/.ssh/config`, `-J`, `-L` and interactive prompts all behave
exactly as they always do. Kekkai consumes its own `--config`, `--port`, and
`--user` options; OpenSSH's `-p N` is an alias for the remote port reached
through the overlay. Other OpenSSH flags, an explicit destination, and the
remote command keep their usual order.

It refuses before starting anything when the netmap does not grant the edge:

```
$ kekkai ssh judah --port 8080
kekkai: the netmap does not grant main-2 -> judah :ssh on port 8080.
  Reachability is the control plane's decision, not this command's — publish a
  policy grant with :capabilities [:overlay :ssh] and :ports [8080].
```

Exit codes are the sysexits ones an operator can branch on: `78` the netmap
does not allow it, `69` no session (connectivity, not policy), `64` usage,
`70` everything else.

**The destination is supplied by this command**, after the options and before
any remote command — `ssh [options] destination [command]` is positional, and
getting that wrong is not subtle: an earlier version appended the destination
last and `kekkai ssh judah … 'echo hi; hostname'` failed with `hostname
contains invalid characters`, because ssh had read the remote command as the
host. `ssh-argv` is unit-tested for exactly that shape.

## `kekkai netmap publish`

Takes **one file describing the whole tailnet** and writes one signed netmap per
node. Whole-plane on purpose: a netmap is a projection, and projecting each
node from a separate file is how two nodes end up disagreeing about who is in
the tailnet.

```clojure
{:version 1
 :nodes [{:id "judah" :user "jun" :tailnet "fleet" :tags ["tag:server"]
          :static-pub "…" :overlay-ip "100.64.0.2"
          :key-expiry 4102444800 :status "authorized"} …]
 :plane {:policies {"fleet" {:tag-owners {"tag:server" ["jun"]}
                             :grants [{:src ["tag:laptop"] :dst ["tag:server"]
                                       :ports [22]
                                       :capabilities [:overlay :ssh]}]}}
         :peerings []}
 :relays [{:name "judah" :host "…" :port 41999 :key "…"}]}
```

`:capabilities` is opt-in per grant — the default is `[:overlay]` alone, so
widening a port list never quietly widens what may be done through it.

Exclusions are printed, not buried: a node absent from a netmap and a node
denied by one are different states, and only the operator knows which was
intended.

## `kekkai netmap verify`

Answers the question an operator actually has — not "is this signed" but "what
does it let this node reach":

```
$ kekkai netmap verify netmap-main-2.signed.edn --authority MCowBQ…
signature ok — signed by 21e1-c803-4801-93aa
tailnet fleet v1   self main-2

  → judah  100.64.0.2  overlay,ssh
```

`--authority` is required and is **never read from the envelope**: an envelope
carrying the only copy of its signer's key would authenticate itself.

## `kekkai desired publish` / `pull`

Publishes arbitrary signed desired state without a JVM or hosted control
plane. The input is the same contract the JVM Kekkai verifier accepts:

```clojure
{:kind :murakumo/apps
 :subject "murakumo/fleet/apps"
 :epoch 1
 :previous-cid nil
 :payload {:murakumo/schema "murakumo.desired-apps/v1" :apps []}}
```

```bash
kekkai desired publish --input desired.edn --authority authority.edn \
  --roots ssh://asher/var/lib/kekkai,ssh://judah/var/lib/kekkai \
  --min-copies 2

kekkai desired pull --subject murakumo/fleet/apps \
  --authority authority.edn \
  --roots ssh://asher/var/lib/kekkai,ssh://judah/var/lib/kekkai \
  --kind murakumo/apps
```

Each immutable envelope and payload has a CIDv1; mutable heads carry only the
latest CID/epoch. Equal-epoch disagreement, rollback, an untrusted signer, or a
failed mirror quorum stops the command. Roots can be local paths or validated
`ssh://host/absolute/path` locations. No Cloudflare service is involved.

## Two things learned by running it

**Give the relay its own keypair.** `kekkai relay --config X` uses `X`'s
`:static`, so pointing it at a node's config makes the relay and that node one
identity. Doing that produced sessions that established and then stopped, and
nothing in the logs said why — which is also why `up --verbose` and the relay's
registration log exist now. A CLI whose session dies silently is not an
operator tool.

**Put the relay where peers can reach it.** Measured on this fleet: UDP flowed
workstation→node but not the reverse, so a relay on the workstation was
reachable by nobody. Both peers dial the relay, so it belongs on the reachable
side — which is also the honest deployment shape.

## Running it

Siblings are expected next to this checkout (`../kekkai`, `../kekkai-node`,
`../bytes`, `../noise`, `../org-ietf-dns`, `../org-ietf-turn`,
`../tech-ipfs-specs-ipns`). The classpath is
explicit because an `nbb.edn` with `:deps` makes nbb shell out to `bb`, which
this workspace retired as a script host (ADR-2607173000).

```bash
npm install
npm run kekkai -- ssh judah      # or kbb --backend sci --classpath "…" bin/kekkai.cljk ssh judah
npm test
```

Apache-2.0.
