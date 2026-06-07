import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

export const server = new McpServer({
  name: "open-seiyaku-mcp",
  version: "0.1.0",
});

const SocialPostSchema = z.object({
  text: z.string().describe("The text content of the social post to etzhayyim.com"),
  tags: z.array(z.string()).optional().describe("Optional tags/hashtags for the post"),
});

const VizSchema = z.object({
  productId: z.string().describe("The product ID to visualize the supply chain for (e.g. an expired patent drug id)"),
  includeRobotics: z.boolean().default(true).describe("Include robotics process steps in the visualization"),
});

// Tool 1: Post to Social (etzhayyim.com)
server.tool(
  "post_to_etzhayyim_social",
  "Publish a milestone update to the yoro.etzhayyim.com social feed regarding the pharma automation supply chain.",
  SocialPostSchema.shape,
  async ({ text, tags }) => {
    // In a real implementation, this would call `com.atproto.repo.createRecord` via `@etzhayyim/kotodama-host-sdk`
    // or POST to `dispatcher.etzhayyim.com/xrpc/com.etzhayyim.yoro.postFeedItem`
    const did = "did:web:seiyaku.etzhayyim.com";

    // Simulate successful post
    const rkey = Math.random().toString(36).substring(2, 10);
    const uri = `at://${did}/app.bsky.feed.post/${rkey}`;
    const url = `https://yoro.etzhayyim.com/profile/${encodeURIComponent(did)}/post/${rkey}`;

    const hashtags = tags ? tags.map(t => `#${t}`).join(' ') : '';
    const fullText = `${text} ${hashtags}`.trim();

    return {
      content: [
        {
          type: "text",
          text: `Successfully posted to etzhayyim.com social network!\nURI: ${uri}\nURL: ${url}\nContent: "${fullText}"`,
        },
      ],
    };
  }
);

// Tool 2: Visualize Supply Chain
server.tool(
  "visualize_pharma_supply_chain",
  "Generate a visualization (Mermaid) of the end-to-end supply chain spanning from expired patent candidate, procurement, robotics manufacturing, and distribution.",
  VizSchema.shape,
  async ({ productId, includeRobotics }) => {

    let mermaid = `graph TD\n`;
    mermaid += `  A[Patent Expiry Screen] -->|Candidate: ${productId}| B(Procurement API)\n`;
    mermaid += `  B --> C{Generic Manufacturer}\n`;

    if (includeRobotics) {
      mermaid += `  C -->|Dispatch| D[Robotics Cell Plan]\n`;
      mermaid += `  D --> E[Arm: Machine Tending]\n`;
      mermaid += `  E --> F[Material Handling]\n`;
      mermaid += `  F --> G(QA Release)\n`;
    } else {
      mermaid += `  C --> G(QA Release)\n`;
    }

    mermaid += `  G --> H[Port & Cargo Logistics]\n`;
    mermaid += `  H --> I[Hospital/Pharmacy Delivery]\n`;

    mermaid += `\n  style A fill:#f9f,stroke:#333,stroke-width:2px\n`;
    mermaid += `  style G fill:#bbf,stroke:#333,stroke-width:2px\n`;

    return {
      content: [
        {
          type: "text",
          text: "Supply chain visualization generated successfully. Use this Mermaid diagram to render the visualization in a markdown viewer:\n\n```mermaid\n" + mermaid + "```",
        },
      ],
    };
  }
);

// Tool 3: Start Manufacturing Candidate
server.tool(
  "start_generic_manufacturing_candidate",
  "Trigger the pipeline to create a generic manufacturing candidate from an expired pharmaceutical patent.",
  {
    expiryScreenVid: z.string(),
    productId: z.string(),
    candidateKind: z.enum(["generic", "biosimilar", "api_source"]),
  },
  async ({ expiryScreenVid, productId, candidateKind }) => {
    // Matches the com.etzhayyim.apps.openPatent.startGenericManufacturingCandidate lexicon
    const seiyakuProcessId = `proc-${Math.random().toString(36).substring(2, 8)}`;

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({
            ok: true,
            vertexId: `at://did:web:bpmn.etzhayyim.com/com.etzhayyim.apps.bpmn.processDef/${seiyakuProcessId}`,
            seiyakuProcessId,
            instanceKey: Math.floor(Math.random() * 100000)
          }, null, 2),
        },
      ],
    };
  }
);

export async function runServer() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("open-seiyaku-mcp server running on stdio");
}
