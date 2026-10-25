export type JsonValue = null | boolean | number | string | JsonValue[] | {
    [key: string]: JsonValue;
};
export type SVGraphNode = {
    node_id: string;
    tag: string;
    attributes: Record<string, string>;
    data: Record<string, string>;
    metadata: {
        text?: string;
        json?: JsonValue;
    };
    dependencies: Dependency[];
    children: SVGraphNode[];
    text: string | null;
};
export type Dependency = {
    kind: string;
    source: string;
    target: string;
    attribute: string;
};
export type SVGraphPresentationProjection = {
    kind: "svgraph-presentation";
    slide_size: [number, number];
    slides: SlideRecord[];
    parts: PartRecord[];
    masters: TemplateRecord[];
    layouts: TemplateRecord[];
    guides: GuideRecord[];
    rulers: RulerRecord[];
    text_styles: TextStyleRecord[];
    metadata: Record<string, JsonValue>;
};
export type SlideRecord = {
    slide_id: string;
    node_id: string;
    title: string | null;
    view_box: [number, number, number, number];
    data: Record<string, string>;
    metadata: {
        text?: string;
        json?: JsonValue;
    };
};
export type PartRecord = {
    part_name: string;
    content_type: string;
    kind: string;
    source_node_id: string | null;
};
export type TemplateRecord = {
    template_id: string;
    kind: string;
    node_id: string | null;
    data: Record<string, string>;
    metadata: JsonValue;
};
export type GuideRecord = {
    guide_id: string;
    orientation: string;
    position: number;
    unit: string;
    node_id: string | null;
};
export type RulerRecord = {
    ruler_id: string;
    orientation: string;
    origin: number;
    unit: string;
    spacing: number | null;
    node_id: string | null;
};
export type TextStyleRecord = {
    style_id: string;
    role: string;
    properties: Record<string, JsonValue>;
    node_id: string | null;
};
export type SVGraphDocument = {
    kind: "svgraph";
    version: string;
    root: SVGraphNode;
    metadata: {
        text?: string;
        json?: JsonValue;
    };
    dependencies: Dependency[];
    coverage: SvgCoverage;
    presentation: SVGraphPresentationProjection;
};
export type SVGraphSidecar = {
    kind: "svgraph-sidecar";
    version: string;
    source_svg: string;
    metadata: {
        text?: string;
        json?: JsonValue;
    };
    dependencies: Dependency[];
    coverage: SvgCoverage;
    presentation: SVGraphPresentationProjection;
};
export type OfficeCausalNode = {
    id: `ocz1:${string}`;
    kind: "document" | "slide" | "shape" | "table" | "image" | "entity" | "claim";
    part: string;
    path: string;
    label?: string;
    text?: string;
    bbox?: {
        x: number;
        y: number;
        w: number;
        h: number;
        unit: "px";
    };
    tags?: string[];
};
export type OfficeCausalEdge = {
    id: string;
    kind: "contains" | "references" | "mentions" | "causes";
    from: `ocz1:${string}`;
    to: `ocz1:${string}`;
    weight?: number;
    causal?: {
        polarity: "+" | "-" | "?";
        mechanism: string;
        confidence: number;
        evidence: {
            nodeId: `ocz1:${string}`;
            quote: string;
        }[];
        status: "hypothesis" | "supported" | "refuted";
    };
};
export type OfficeCausalPayload = {
    version: 1;
    generator: "office-causal";
    nodes: OfficeCausalNode[];
    edges: OfficeCausalEdge[];
    analysis?: {
        svgraph?: {
            version: string;
            coverage: SvgCoverage;
            presentation: SVGraphPresentationProjection;
        };
    };
};
export type AssistantPatchOp = {
    op: string;
    node_id: string;
    [key: string]: JsonValue;
};
export type AssistantPatchProposal = {
    summary: string;
    ops: AssistantPatchOp[];
    confidence: number;
};
export type AssistantPatchValidation = {
    status: "accepted" | "rejected";
    errors: string[];
};
export type AssistantPatchDiff = {
    op: string;
    node_id: string;
    field: string;
    before: JsonValue;
    after: JsonValue;
    status: "pending" | "unchanged" | "unsupported";
};
export type AssistantBackendPolicy = "webgpu" | "wasm" | "disabled";
export type SvgCoverage = {
    total_elements: number;
    convertible_elements: number;
    ignored_elements: number;
    unsupported_elements: Record<string, number>;
    unsupported_attributes: Record<string, number>;
    unsupported_path_commands: Record<string, number>;
    estimated_element_coverage: number;
};
export declare const assistantAllowedOps: readonly ["mark-slide", "set-data", "set-metadata", "mark-table", "mark-cell", "bind-relation", "set-reading-order"];
export declare function buildSVGraph(svgText: string): SVGraphDocument;
export declare function buildSVGraphSidecar(svgraph: SVGraphDocument, svgText?: string): SVGraphSidecar;
export declare function buildOfficeCausalPayload(svgraph: SVGraphDocument): OfficeCausalPayload;
export declare function buildOfficeCausalJsonl(svgraph: SVGraphDocument): string;
export declare function assistantPatchProposal(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): AssistantPatchProposal;
export declare function buildSVGraphAssistantPrompt(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): string;
export declare function parseAssistantPatchProposal(value: unknown): AssistantPatchProposal;
export declare function validateAssistantPatch(proposal: AssistantPatchProposal, svgraph: SVGraphDocument): AssistantPatchValidation;
export declare function assistantPatchDiff(proposal: AssistantPatchProposal, svgraph: SVGraphDocument): AssistantPatchDiff[];
export declare function applyAssistantPatch(svgText: string, proposal: AssistantPatchProposal, svgraph: SVGraphDocument): string;
export declare function svgToPptx(svgText: string): Uint8Array;
export declare function svgToDrawingMl(svgText: string): string;
export declare function drawingMlToSvg(drawingMlText: string): string;
export declare function initSVGraphEditor(): void;
