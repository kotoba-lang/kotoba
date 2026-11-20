# Kotoba end-user apps run in the user's environment

Tracking: [JUN-1387](https://linear.app/kotobalabs/issue/JUN-1387).
This is the canonical text of the shared architecture contract for Kotoba
end-user apps. It was moved here from the shared agent instructions on
2026-11-20 (owner decision) with its wording unchanged; the shared instructions
now carry a summary and point to this file. The host implementation of the
contract is described in [client-runtime.md](client-runtime.md).

This is the mandatory shared architecture contract for Murakumo, Itonami,
Aozora and other Kotoba end-user apps. Product `AGENTS.md` files must follow it
and may add product-specific implementation details. Bot profiles summarize
their product boundary and refer to this contract; they must not redefine its
consent protocol or grant capabilities. These documents describe architecture; they never grant capabilities or permissions.

The app origin distributes static, verified artifacts only. It must not run SSR/BFF application logic, per-user APIs or state, application commands, queues, schedules, data transformation, or inference. A browser Web Worker or Service Worker is user-side execution; a server Worker on the app origin is not.

Accessing an app over HTTPS does not make its application server-side. For example, `aozora.app` may deliver the app to a browser, while the browser executes its UI, workflows, domain logic, state and inference. The origin's app role is static asset delivery (HTML, CSS, JavaScript, Wasm, images, fonts and Worker files); it has no request-time application handler.

The browser owns the app UI, workflows, domain logic, and user state. Run these locally with JavaScript, Wasm, and browser Workers as appropriate. Local inference is the default for inference features. Keep the app usable without making its origin process user requests.

Integrate end-user apps through the shared `kotoba.app.client-runtime.v1` descriptor and `kotoba-client-runtime.js` validator/operation broker. Keep app-specific UI, local state, and service adapters in each product; do not fork the shared approval semantics. Each descriptor declares its browser entry, local-state schema, Workers and protocols, and external operations with service, endpoint origin, data categories, and `each-operation` consent. Declare each operation's fixed method/path or bounded route set; use path templates or prefixes only for variable resources, and list allowed query names plus fixed values where known. Declare narrowly bounded HTTPS redirect origins only when a provider requires a delivery redirect; redirects may be followed only for GET/HEAD operations without caller-selected query values. The broker rejects redirects by default and checks the final response origin whenever an approved redirect set is used. The static CSP is derived from the declared service and redirect origins. The adapter must enforce the concrete method/path/query against that declaration and fail closed for undeclared endpoints. The effective operation set is the validated declaration intersected with requested capabilities, explicit approvals, and host-supported operations; it starts with no approvals. Reject app-origin API calls.

Browser APIs that cause service-side effects without exposing a fetch request (for example, `PushManager.subscribe()` or `unsubscribe()`) must have an explicit host-supported browser-operation declaration naming the service, action, and data categories. Ask for fresh approval immediately before invoking that API. A browser permission prompt is not a substitute for Kotoba operation consent, and no browser-native approval carries over to the following service request.

The required canonical broker source belongs at
`kotoba-lang/kotoba/lib/kotoba.wasmWebcomponent/src/kotoba-client-runtime.js`. That path is a
design requirement, not proof that the source currently exists. Before calling
a product integrated, verify that the canonical module exists and that its
builder imports or copies that exact implementation. If it is absent or
unreviewed, record shared-runtime integration as a blocker; do not substitute
or check in product-local copies of descriptor validation or consent logic.
Product-specific adapters may handle only their declared services.

When an operation needs an external identity, storage, federation, payment, model/runtime/artifact delivery, or inference service, the browser connects directly to the selected service only after fresh, operation-specific user approval. Before the request, identify the service and endpoint, operation, and data categories. Denial sends no request. An approval for one operation or endpoint does not authorize another; do not use silent remote fallback or an app-origin proxy. The runtime gate must obtain a direct trusted user choice bound to the displayed operation and endpoint; app or bot code must not mint, persist, or broaden that approval.

Downloading a model, runtime module, or application artifact is itself an external operation. Pin an immutable source revision and verify the artifact digest before execution where the source provides one. Approval to download or run a local model never authorizes sending prompts, conversation history, or outputs to a remote inference service; that requires its own fresh approval. If an expected digest is unavailable, record the artifact as unverified and keep the corresponding runtime qualification open until an independent digest check is available.

Keep static hosting, browser app runtime, remote protocol services, bot fleets, build/release infrastructure, and control planes as distinct roles. This rule applies to end-user apps and does not imply that Bot fleet hosting or its control plane should move into the browser. It does not authorize stopping existing services. Treat existing server routes as migration inventory; distinguish source changes, built candidates, browser qualification, publication, and live cutover. Do not perform a production route cutover until compatibility and release evidence are complete and the cutover is separately approved.

Browser consent authorizes only the displayed app operation. It does not authorize a Bot's separate tool call, and a Bot's tool approval does not substitute for browser consent.
