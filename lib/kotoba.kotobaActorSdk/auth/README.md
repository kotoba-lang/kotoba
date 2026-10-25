# @etzhayyim/sdk-auth

PDS session authentication wiring for the Etzhayyim SDK. Provides helpers to inject atproto access/refresh JWTs into Etzhayyim SDK instances for both CF Worker (edge) and K8s pod (backend) execution contexts.

## Usage

```ts
import { createAuthedEtzhayyim, extractBearerToken } from "@etzhayyim/sdk-auth";

interface Env {
  ACTOR_DID: string;
  PDS_URL: string;
  L2_RPC_URL?: string;
  PDS_ACCESS_JWT?: string;
  PDS_REFRESH_JWT?: string;
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const bearerToken = extractBearerToken(req);
    const e = createAuthedEtzhayyim({ env, bearerToken });
    const result = await e.read({ collection: "com.etzhayyim.apps.example.item" });
    return new Response(JSON.stringify(result), {
      headers: { "content-type": "application/json" },
    });
  }
} satisfies ExportedHandler<Env>;
```

Session precedence: incoming Authorization header → env.PDS_ACCESS_JWT (actor service identity) → anonymous (read-only).
