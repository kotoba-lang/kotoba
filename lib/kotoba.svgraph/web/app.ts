const emuPerPx = 9525;

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export type SVGraphNode = {
  node_id: string;
  tag: string;
  attributes: Record<string, string>;
  data: Record<string, string>;
  metadata: { text?: string; json?: JsonValue };
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
  metadata: { text?: string; json?: JsonValue };
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
  metadata: { text?: string; json?: JsonValue };
  dependencies: Dependency[];
  coverage: SvgCoverage;
  presentation: SVGraphPresentationProjection;
};

export type SVGraphSidecar = {
  kind: "svgraph-sidecar";
  version: string;
  source_svg: string;
  metadata: { text?: string; json?: JsonValue };
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
  bbox?: { x: number; y: number; w: number; h: number; unit: "px" };
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
    evidence: { nodeId: `ocz1:${string}`; quote: string }[];
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

type AssistantWorkerEvent =
  | { type: "status"; status: string }
  | { type: "proposal"; proposal: AssistantPatchProposal; raw: string }
  | { type: "error"; error: string };

export type SvgCoverage = {
  total_elements: number;
  convertible_elements: number;
  ignored_elements: number;
  unsupported_elements: Record<string, number>;
  unsupported_attributes: Record<string, number>;
  unsupported_path_commands: Record<string, number>;
  estimated_element_coverage: number;
};

export const assistantAllowedOps = ["mark-slide", "set-data", "set-metadata", "mark-table", "mark-cell", "bind-relation", "set-reading-order"] as const;
const assistantAllowedOpNames: readonly string[] = assistantAllowedOps;
const assistantModelId = "onnx-community/gemma-4-e2b-it-ONNX";

type Shape =
  | RectShape
  | EllipseShape
  | LineShape
  | TextShape
  | TableShape
  | FreeformShape
  | ImageShape;

type BaseShape = {
  id: number;
  kind: string;
  name: string;
  data: Record<string, string>;
};

type Box = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type Viewport = {
  width: number;
  height: number;
};

type RectShape = BaseShape & {
  kind: "rect";
  x: number;
  y: number;
  width: number;
  height: number;
  rx: number;
  fill: string | null;
  fillAlpha: number | null;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  strokeDashoffset: number | null;
};

type EllipseShape = BaseShape & {
  kind: "ellipse";
  x: number;
  y: number;
  width: number;
  height: number;
  fill: string | null;
  fillAlpha: number | null;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
};

type LineShape = BaseShape & {
  kind: "line";
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  strokeDashoffset: number | null;
  relation: boolean;
  startId: number | null;
  endId: number | null;
  markerStart: boolean;
  markerEnd: boolean;
};

type TextShape = BaseShape & {
  kind: "text";
  x: number;
  y: number;
  width: number;
  height: number;
  text: string;
  fill: string | null;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  fontSize: number;
  fontFamily: string;
  bold: boolean;
  italic: boolean;
  fontVariant: string | null;
  underline: boolean;
  underlineStyle: string | null;
  underlineColor: string | null;
  underlineAlpha: number | null;
  underlineThickness: number | null;
  strike: boolean;
  baselineShift: string | null;
  letterSpacing: number | null;
  rotation: number | null;
  direction: string | null;
  anchor: string | null;
  baseline: string | null;
  runs: TextRun[];
};

type TextRun = {
  text: string;
  breakBefore: boolean;
  preserveSpace: boolean;
  fill: string | null;
  fillAlpha: number | null;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  fontSize: number;
  fontFamily: string;
  bold: boolean;
  italic: boolean;
  fontVariant: string | null;
  underline: boolean;
  underlineStyle: string | null;
  underlineColor: string | null;
  underlineAlpha: number | null;
  underlineThickness: number | null;
  strike: boolean;
  baselineShift: string | null;
  letterSpacing: number | null;
};

type FreeformShape = BaseShape & {
  kind: "freeform";
  points: [number, number][];
  closed: boolean;
  fill: string | null;
  fillAlpha: number | null;
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  strokeDashoffset: number | null;
  markerStart: boolean;
  markerEnd: boolean;
};

type ImageShape = BaseShape & {
  kind: "image";
  x: number;
  y: number;
  width: number;
  height: number;
  href: string;
  alpha: number | null;
  srcRect: [number, number, number, number] | null;
  rotation: number | null;
  flipH: boolean;
  flipV: boolean;
};

type TableShape = BaseShape & {
  kind: "table";
  x: number;
  y: number;
  columns: number[];
  rows: number[];
  cells: TableCell[];
};

type TableCell = {
  row: number;
  col: number;
  colSpan: number;
  rowSpan: number;
  text: string;
  runs: TextRun[];
  fill: string | null;
  fillAlpha: number | null;
  textFill: string | null;
  textFillAlpha: number | null;
  textBold: boolean;
  textAlign: string | null;
  verticalAlign: string | null;
  paddingLeft: number;
  paddingRight: number;
  paddingTop: number;
  paddingBottom: number;
  direction: string | null;
  nowrap: boolean;
  borderLeft: TableBorder;
  borderRight: TableBorder;
  borderTop: TableBorder;
  borderBottom: TableBorder;
};

type TableBorder = {
  stroke: string | null;
  strokeAlpha: number | null;
  strokeWidth: number;
  strokeLineCap: string | null;
  strokeLineJoin: string | null;
  strokeMiterlimit: number | null;
  strokeDasharray: string | null;
  compound: string | null;
};

type HtmlFill = {
  color: string;
  alpha: number | null;
};

type Matrix = [number, number, number, number, number, number];

type SvgStyle = {
  customProperties?: Record<string, string>;
  fill?: string | null;
  fillAlpha?: number | null;
  fillRule?: string | null;
  stroke?: string | null;
  strokeAlpha?: number | null;
  strokeWidth?: number;
  color?: string | null;
  colorAlpha?: number | null;
  strokeLineCap?: string | null;
  strokeLineCapSource?: string | null;
  strokeLineJoin?: string | null;
  strokeLineJoinSource?: string | null;
  strokeMiterlimit?: number | null;
  strokeDasharray?: string | null;
  strokeDashoffset?: number | null;
  tableBorderCompound?: string | null;
  imageAlpha?: number | null;
  display?: string | null;
  visibility?: string | null;
  fontSize?: number;
  fontFamily?: string;
  fontWeight?: string;
  fontStyle?: string;
  fontVariant?: string | null;
  textDecoration?: string;
  textDecorationColor?: string | null;
  textDecorationAlpha?: number | null;
  textDecorationThickness?: number | null;
  textTransform?: string | null;
  textAnchor?: string | null;
  textBaseline?: string | null;
  baselineShift?: string | null;
  letterSpacing?: number | null;
  wordSpacing?: number | null;
  textLength?: number | null;
  lengthAdjust?: string | null;
  rotate?: number | null;
  direction?: string | null;
  pathLength?: number | null;
  markerStart?: boolean;
  markerEnd?: boolean;
  markerMid?: boolean;
  markerMidSource?: "marker" | "marker-mid" | null;
  clipPath?: string | null;
  overflow?: string | null;
  transform?: string | null;
  transformOrigin?: string | null;
  vectorEffect?: string | null;
  isolation?: string | null;
  mixBlendMode?: string | null;
  tableCellPadding?: number;
  tableCellPaddingLeft?: number;
  tableCellPaddingRight?: number;
  tableCellPaddingTop?: number;
  tableCellPaddingBottom?: number;
  tableCellTextAlign?: string | null;
  tableCellVerticalAlign?: string | null;
  tableCellNowrap?: boolean;
  tableBorderLeft?: TableBorder | null;
  tableBorderRight?: TableBorder | null;
  tableBorderTop?: TableBorder | null;
  tableBorderBottom?: TableBorder | null;
};

type CssRule = {
  selector: string;
  declarations: Record<string, CssDeclaration>;
  specificity: [number, number, number];
  order: number;
};

type CssDeclaration = {
  value: string;
  important: boolean;
};

type PreparedSlide = {
  xml: string;
  rels: string;
  media: Record<string, Uint8Array>;
};

const rootFontSize = 16;

const namedColors: Record<string, string | null> = {
  aliceblue: "#f0f8ff",
  antiquewhite: "#faebd7",
  aqua: "#00ffff",
  aquamarine: "#7fffd4",
  azure: "#f0ffff",
  beige: "#f5f5dc",
  bisque: "#ffe4c4",
  black: "#000000",
  blanchedalmond: "#ffebcd",
  blue: "#0000ff",
  blueviolet: "#8a2be2",
  brown: "#a52a2a",
  burlywood: "#deb887",
  cadetblue: "#5f9ea0",
  chartreuse: "#7fff00",
  chocolate: "#d2691e",
  coral: "#ff7f50",
  cornflowerblue: "#6495ed",
  cornsilk: "#fff8dc",
  crimson: "#dc143c",
  cyan: "#00ffff",
  darkblue: "#00008b",
  darkcyan: "#008b8b",
  darkgoldenrod: "#b8860b",
  darkgray: "#a9a9a9",
  darkgreen: "#006400",
  darkgrey: "#a9a9a9",
  darkkhaki: "#bdb76b",
  darkmagenta: "#8b008b",
  darkolivegreen: "#556b2f",
  darkorange: "#ff8c00",
  darkorchid: "#9932cc",
  darkred: "#8b0000",
  darksalmon: "#e9967a",
  darkseagreen: "#8fbc8f",
  darkslateblue: "#483d8b",
  darkslategray: "#2f4f4f",
  darkslategrey: "#2f4f4f",
  darkturquoise: "#00ced1",
  darkviolet: "#9400d3",
  deeppink: "#ff1493",
  deepskyblue: "#00bfff",
  dimgray: "#696969",
  dimgrey: "#696969",
  dodgerblue: "#1e90ff",
  firebrick: "#b22222",
  floralwhite: "#fffaf0",
  forestgreen: "#228b22",
  fuchsia: "#ff00ff",
  gainsboro: "#dcdcdc",
  ghostwhite: "#f8f8ff",
  gold: "#ffd700",
  goldenrod: "#daa520",
  gray: "#808080",
  green: "#008000",
  greenyellow: "#adff2f",
  grey: "#808080",
  honeydew: "#f0fff0",
  hotpink: "#ff69b4",
  indianred: "#cd5c5c",
  indigo: "#4b0082",
  ivory: "#fffff0",
  khaki: "#f0e68c",
  lavender: "#e6e6fa",
  lavenderblush: "#fff0f5",
  lawngreen: "#7cfc00",
  lemonchiffon: "#fffacd",
  lightblue: "#add8e6",
  lightcoral: "#f08080",
  lightcyan: "#e0ffff",
  lightgoldenrodyellow: "#fafad2",
  lightgray: "#d3d3d3",
  lightgreen: "#90ee90",
  lightgrey: "#d3d3d3",
  lightpink: "#ffb6c1",
  lightsalmon: "#ffa07a",
  lightseagreen: "#20b2aa",
  lightskyblue: "#87cefa",
  lightslategray: "#778899",
  lightslategrey: "#778899",
  lightsteelblue: "#b0c4de",
  lightyellow: "#ffffe0",
  lime: "#00ff00",
  limegreen: "#32cd32",
  linen: "#faf0e6",
  magenta: "#ff00ff",
  mediumaquamarine: "#66cdaa",
  mediumblue: "#0000cd",
  mediumorchid: "#ba55d3",
  mediumpurple: "#9370db",
  mediumseagreen: "#3cb371",
  mediumslateblue: "#7b68ee",
  mediumspringgreen: "#00fa9a",
  mediumturquoise: "#48d1cc",
  mediumvioletred: "#c71585",
  midnightblue: "#191970",
  mintcream: "#f5fffa",
  mistyrose: "#ffe4e1",
  moccasin: "#ffe4b5",
  navajowhite: "#ffdead",
  navy: "#000080",
  oldlace: "#fdf5e6",
  olive: "#808000",
  olivedrab: "#6b8e23",
  orange: "#ffa500",
  orangered: "#ff4500",
  orchid: "#da70d6",
  palegoldenrod: "#eee8aa",
  palegreen: "#98fb98",
  paleturquoise: "#afeeee",
  palevioletred: "#db7093",
  papayawhip: "#ffefd5",
  peachpuff: "#ffdab9",
  peru: "#cd853f",
  pink: "#ffc0cb",
  plum: "#dda0dd",
  powderblue: "#b0e0e6",
  purple: "#800080",
  red: "#ff0000",
  rosybrown: "#bc8f8f",
  royalblue: "#4169e1",
  saddlebrown: "#8b4513",
  salmon: "#fa8072",
  sandybrown: "#f4a460",
  seagreen: "#2e8b57",
  seashell: "#fff5ee",
  sienna: "#a0522d",
  silver: "#c0c0c0",
  skyblue: "#87ceeb",
  slateblue: "#6a5acd",
  slategray: "#708090",
  slategrey: "#708090",
  snow: "#fffafa",
  springgreen: "#00ff7f",
  steelblue: "#4682b4",
  tan: "#d2b48c",
  teal: "#008080",
  thistle: "#d8bfd8",
  tomato: "#ff6347",
  transparent: null,
  turquoise: "#40e0d0",
  violet: "#ee82ee",
  wheat: "#f5deb3",
  white: "#ffffff",
  whitesmoke: "#f5f5f5",
  yellow: "#ffff00",
  yellowgreen: "#9acd32",
};

const sampleSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720">
  <metadata>{"presentation":{"slideSize":{"width":1280,"height":720},"masters":[{"id":"brand-master"}],"layouts":[{"id":"title-content","master":"brand-master"}],"guides":[{"id":"safe-left","orientation":"vertical","position":90}],"rulers":[{"id":"x","orientation":"horizontal","origin":0,"spacing":16}],"textStyles":{"title":{"fontFamily":"Aptos Display","fontSize":54,"bold":true},"lead":{"fontFamily":"Aptos","fontSize":28},"body":{"fontFamily":"Aptos","fontSize":18}}}}</metadata>
  <style>
    table.cascade-table td { background-color: #e0f2fe; color: #0c4a6e; }
    #cascade-cell { background-color: #fef3c7; color: #78350f; border-left: 4px solid #d97706 !important; }
    .cascade-table tr > * { background-color: #fee2e2; color: #991b1b; }
    table.col-fill col.hot { background-color: #dbeafe; }
  </style>
  <g id="cover" data-kind="slide" data-title="SVGraph Cover">
    <rect width="1280" height="720" fill="#f8fafc"/>
    <rect x="90" y="96" width="500" height="210" rx="22" fill="#ccfbf1" stroke="#0f766e" stroke-width="4"/>
    <text x="128" y="184" font-size="54" font-family="Arial" font-weight="700" fill="#134e4a">SVGraph</text>
    <text x="130" y="248" font-size="28" font-family="Arial" fill="#334155">SVG as editable SVGraph presentation</text>
    <circle id="api" data-kind="service" cx="770" cy="230" r="70" fill="#dbeafe" stroke="#2563eb" stroke-width="4"/>
    <rect id="deck" data-kind="presentation" x="910" y="160" width="190" height="140" rx="16" fill="#fee2e2" stroke="#b42318" stroke-width="4"/>
    <line data-kind="relation" x1="840" y1="230" x2="910" y2="230" stroke="#475467" stroke-width="5"/>
  </g>
  <g id="table-slide" data-kind="slide" data-title="Native Table Candidate">
    <rect width="1280" height="720" fill="#ffffff"/>
    <text x="90" y="90" font-size="40" font-family="Arial" font-weight="700" fill="#17202a">Table semantics stay in SVGraph</text>
    <g id="table" data-kind="table" transform="translate(90 150)">
      <rect data-kind="cell" data-row="0" data-col="0" data-colspan="2" data-text="Merged header" width="520" height="80" fill="#e6f4f1" stroke="#0f766e" stroke-width="2" stroke-dasharray="4 2" stroke-linecap="round" stroke-linejoin="round"/>
      <rect data-kind="cell" data-row="1" data-col="0" data-rowspan="2" data-text="Tall label" y="80" width="260" height="160" fill="#f0fdf4" stroke="#0f766e" stroke-width="2"/>
      <rect data-kind="cell" data-row="1" data-col="1" data-text="Value" x="260" y="80" width="260" height="80" fill="#ffffff" stroke="#0f766e"/>
      <rect data-kind="cell" data-row="2" data-col="1" data-text="Total" x="260" y="160" width="260" height="80" fill="#ffffff" stroke="#0f766e"/>
    </g>
  </g>
  <g id="html-table-slide" data-kind="slide" data-title="HTML Table Candidate">
    <rect width="1280" height="720" fill="#ffffff"/>
    <text x="90" y="90" font-size="40" font-family="Arial" font-weight="700" fill="#17202a">foreignObject table becomes native</text>
    <foreignObject id="html-table" x="90" y="150" width="620" height="250">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table class="cascade-table" cellpadding="6">
          <caption style="font-size:18px;color:#2563eb">HTML metrics <strong>native</strong></caption>
          <colgroup>
            <col style="width:35%"/>
            <col style="width:25%"/>
            <col style="width:40%"/>
          </colgroup>
          <tr style="height:70px">
            <th colspan="2" style="background-color:#dbeafe;color:#1e3a8a;border:2px dashed #2563eb">Merged HTML header</th>
            <th style="background-color:#e0f2fe;color:#0c4a6e;border:2px solid #0284c7">Owner</th>
          </tr>
          <tr>
            <td rowspan="2" style="background-color:#dcfce7;color:#14532d;border:2px solid #16a34a;font-weight:700">Roadmap</td>
            <td align="center" valign="top" style="background-color:#ffffff;color:#111827;border:1px solid #94a3b8;white-space:nowrap;direction:rtl;padding:2px 6px 3px 8px;text-transform:lowercase">SVGraph <strong>rich</strong> <em>runs</em> <strong style="font-weight:400">plain</strong> <span style="color:#dc2626;font-variant:small-caps;word-spacing:6px;text-decoration-line:underline;text-decoration-style:dashed;text-transform:uppercase">red gap</span></td>
            <td style="background-color:#f8fafc;color:#111827;border:1px solid #94a3b8;border-right:3px dotted #dc2626;border-top:4px double #2563eb;border-bottom-style:dashed;border-bottom-width:2px;border-bottom-color:#16a34a">Browser</td>
          </tr>
          <tr>
            <td style="background:padding-box #ffffff;color:#111827;border:hidden 2px #94a3b8;padding:calc(0.5px + 0.5px)">PPTX</td>
            <td id="cascade-cell" style="border:1px solid #94a3b8;border-left:2px solid #dc2626">Cascade</td>
          </tr>
        </table>
      </body>
    </foreignObject>
    <foreignObject id="spaced-html-table" x="760" y="150" width="360" height="150">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table cellspacing="8" style="background:#f8fafc">
          <tr>
            <td style="background-color:#ffffff;color:#111827;border:1px solid #94a3b8">Gap A</td>
            <td style="background-color:#e0f2fe;color:#0c4a6e;border:1px solid #0284c7">Gap B</td>
          </tr>
        </table>
      </body>
    </foreignObject>
    <foreignObject id="col-bg-html-table" x="760" y="340" width="360" height="90">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table class="col-fill">
          <colgroup style="background:#dcfce7">
            <col class="hot"/>
            <col/>
          </colgroup>
          <tr>
            <td>Column</td>
            <td>Group</td>
          </tr>
        </table>
      </body>
    </foreignObject>
    <foreignObject id="aligned-html-table" x="760" y="465" width="360" height="110">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table width="240" height="70" align="right" style="margin-top:8px">
          <tr>
            <td>Aligned</td>
            <td>Frame</td>
          </tr>
        </table>
      </body>
    </foreignObject>
    <foreignObject id="cell-width-html-table" x="760" y="600" width="360" height="80">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table>
          <tr>
            <th style="width:25%">Label</th>
            <th width="270">Value</th>
          </tr>
          <tr>
            <td>First row width</td>
            <td>Native grid</td>
          </tr>
        </table>
      </body>
    </foreignObject>
    <foreignObject id="alpha-html-table" style="x:90px;y:465px;width:360px;height:90px">
      <body xmlns="http://www.w3.org/1999/xhtml">
        <table>
          <tr>
            <td style="background-color:rgba(37,99,235,0.5);color:rgba(37,99,235,0.5)">RGBA <span style="color:#dc262680">Run</span></td>
            <td style="background:#dc262680;color:#111827;border-style:dotted;border-width:3px;border-color:#dc262680">Hex alpha</td>
          </tr>
        </table>
      </body>
    </foreignObject>
  </g>
  <g id="coverage-slide" data-kind="slide" data-title="Browser SVG Coverage" style="stroke:#334155;stroke-width:4;fill:#fde68a">
    <defs>
      <rect id="reused-chip" width="170" height="70" rx="14"/>
      <clipPath id="bar-clip"><rect style="x:950px;y:500px;width:150px;height:70px;transform:translate(10px,0)"/></clipPath>
      <clipPath id="bbox-clip" clipPathUnits=" OBJECTBOUNDINGBOX "><rect style="x:0.15;y:0.15;width:0.7;height:0.7"/></clipPath>
      <clipPath id="group-clip"><rect x="1150" y="615" width="70" height="50"/></clipPath>
      <rect id="hidden-filtered-use-target" width="10" height="8" fill="none" stroke="none" filter="url(#blur)"/>
      <linearGradient id="linear-fallback"><stop offset="0" stop-color="#ef4444"/><stop offset="1" stop-color="#3b82f6"/></linearGradient>
      <radialGradient id="radial-fallback"><stop offset="0" stop-color="#fef08a"/><stop offset="1" stop-color="#16a34a"/></radialGradient>
      <linearGradient id="empty-gradient" spreadMethod="repeat" gradientUnits="userSpaceOnUse" gradientTransform="rotate(15)"/>
      <linearGradient id="missing-base-gradient" href="#missing-base"><stop offset="0" stop-color="#14b8a6"/></linearGradient>
      <pattern id="pattern-fallback" width="12" height="12" patternUnits="userSpaceOnUse">
        <rect width="12" height="12" fill="#f97316"/>
        <circle cx="6" cy="6" r="4" fill="#22c55e"/>
      </pattern>
      <marker id="dot-marker" viewBox="0 0 10 10"><circle cx="5" cy="5" r="4"/></marker>
      <symbol id="viewbox-icon" viewBox="-5 -5 10 10">
        <circle cx="0" cy="0" r="5" fill="#2563eb"/>
      </symbol>
      <symbol id="context-badge" viewBox="0 0 20 10">
        <rect id="context-paint-rect" width="20" height="10" fill="context-stroke" stroke="context-fill" stroke-width="2"/>
      </symbol>
    </defs>
    <style>
      :root { --browser-brand: #0ea5e9; --browser-line: #334155; }
      .accent-use { fill: #fce7f3; stroke: #be185d; stroke-width: 5; }
      g .css-circle { fill: #e0f2fe; stroke: #0369a1; stroke-width: 5; }
      g.var-theme { fill: var(--browser-brand); stroke: var(--browser-line); stroke-width: 5; }
      .var-theme .inherit-box { fill: inherit; stroke: currentColor; color: #dc2626; }
      .css-transform-origin { transform-origin: center; transform: rotate(12deg) skewX(8deg); }
      @media print { .media-rule { fill: #dc2626; } }
      @media screen { .media-rule { fill: #2563eb; stroke: #16a34a; stroke-width: 5; } }
      .relative-font { font-size: 20px; }
      .relative-font .em-text { font-size: 1.5em; }
      .relative-font .calc-text { font-size: calc(8px + 4px); }
      .font-short-title { font: italic small-caps 700 18px/1.2 "Aptos Display", Arial, sans-serif; fill: #111827; }
      .css-positioned-text { x: 900px; y: 412px; dx: 6px; dy: 4px; }
      .css-geom-rect { x: 735px; y: 165px; width: 75px; height: 38px; rx: 8px; fill: #fee2e2; stroke: #b91c1c; stroke-width: 2px; }
      .css-geom-circle { cx: 845px; cy: 184px; r: 19px; fill: #dcfce7; stroke: #15803d; stroke-width: 2px; }
      .css-geom-line { x1: 735px; y1: 220px; x2: 875px; y2: 220px; pathLength: 70; stroke: #0f172a; stroke-width: 4px; stroke-dasharray: 8 4; }
      .css-image-frame { x: 980px; y: 340px; width: 96px; height: 48px; }
      .css-use-frame { x: 500px; y: 385px; width: 80px; height: 40px; }
      .css-nested-frame { x: 610px; y: 385px; width: 80px; height: 40px; }
      .css-overflow-frame { x: 1120px; y: 610px; width: 80px; height: 40px; }
    </style>
    <rect width="1280" height="720" fill="#ffffff" stroke="none"/>
    <text x="90" y="90" text-rendering="optimizeLegibility" style="font-size:40;font-family:Arial;font-weight:700;fill:#17202a">Browser SVG coverage</text>
    <polygon id="tri" points="120,170 300,170 210,315"/>
    <polyline id="zig" points="390,170 460,250 530,170 600,250" style="fill:none;stroke:#dc2626;stroke-linejoin:miter;stroke-miterlimit:6"/>
    <path id="box-path" d="M 690 170 L 900 170 L 900 315 L 690 315 Z" shape-rendering="crisp-edges" paint-order="fill stroke markers" style="fill:#dcfce7;stroke:#15803d"/>
    <rect class="css-geom-rect"/>
    <circle class="css-geom-circle"/>
    <line class="css-geom-line"/>
    <path id="curve-path" d="M 120 520 C 190 430 260 610 330 520 Q 390 445 450 520 T 570 520" style="fill:none;stroke:#ea580c;stroke-width:6"/>
    <path id="arc-path" d="M 640 520 A 90 55 0 0 1 820 520 A 90 55 0 0 1 640 520" style="fill:#fef3c7;stroke:#a16207;stroke-width:5"/>
    <rect id="geometry-lengths" x="calc(50% - 80px)" y="42%" width="10%" height="8%" style="fill:#ecfccb;stroke:#4d7c0f;stroke-width:2pt"/>
    <rect id="negative-radius-fallback" x="900" y="340" width="90" height="44" rx="-3" ry="8" style="fill:#fef9c3;stroke:#854d0e"/>
    <line id="marked-line" x1="980" y1="185" x2="1130" y2="260" style="stroke:#7c3aed;stroke-width:8;marker-end:url(#arrow)"/>
    <line id="non-arrow-marker-line" x1="980" y1="280" x2="1130" y2="300" style="stroke:#475569;stroke-width:5;marker-end:url(#dot-marker)"/>
    <g id="ignored-marker-mid" marker-mid="url(#arrow)"><line x1="980" y1="315" x2="1130" y2="315" stroke="#64748b" stroke-width="3"/></g>
    <image id="pixel" class="css-image-frame" preserveAspectRatio="xMidYMid slice" opacity="35%" image-rendering="pixelated" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/luzQnAAAAABJRU5ErkJggg=="/>
    <circle class="css-circle" cx="1130" cy="388" r="48"/>
    <rect id="clipped-bar" x="930" y="500" width="250" height="70" style="fill:#fecaca;stroke:#991b1b;clip-path:url(#bar-clip)"/>
    <ellipse id="bbox-clipped-ellipse" cx="1090" cy="560" rx="80" ry="50" style="fill:#ede9fe;stroke:#6d28d9;clip-path:url(#bbox-clip)"/>
    <rect id="css-colors" x="740" y="615" width="120" height="50" color-rendering="optimizeQuality" style="color:orange;fill:currentColor;stroke:hsl(210 100% 50%)"/>
    <rect id="display-hidden" x="875" y="615" width="34" height="50" style="display:none;fill:#111827"/>
    <g id="visibility-hidden" visibility="hidden"><rect id="visibility-visible" x="910" y="615" width="34" height="50" visibility="visible" style="fill:#ffffff;stroke:#0f766e;stroke-width:3"/></g>
    <g id="blend-isolation-dedupe" isolation="isolate"><rect x="955" y="615" width="34" height="50" mix-blend-mode="multiply" style="fill:#f8fafc;stroke:#64748b"/></g>
    <g id="hidden-blend-effect" mix-blend-mode="multiply"><rect x="995" y="615" width="34" height="50" opacity="0" style="fill:#111827"/></g>
    <g id="ignored-empty-filter" filter="url(#blur)"/>
    <g id="ignored-group-opacity" opacity=".5"><rect x="1075" y="615" width="10" height="10" opacity="0"/><rect x="1090" y="615" width="10" height="10" fill="none" stroke="none"/></g>
    <path id="ignored-clip-rule" d="M 1000 615 H 1029 V 665 H 1000 Z" clip-rule="evenodd" fill="#f8fafc" stroke="#94a3b8"/>
    <g id="ignored-fill-rule" fill-rule="evenodd"><path d="M 1035 615 H 1069 V 665 H 1035 Z" fill="none" stroke="#475569"/></g>
    <g class="var-theme"><rect class="inherit-box" x="910" y="88" width="105" height="52"/></g>
    <g id="initial-reset-group" fill="#123456" stroke="#abcdef" stroke-width="5" font-size="24" text-anchor="middle">
      <rect id="initial-reset-rect" x="1035" y="155" width="70" height="40" fill="initial" stroke="initial" stroke-width="initial"/>
      <text id="unset-reset-text" x="1070" y="225" fill="unset" text-anchor="unset">Unset</text>
    </g>
    <rect id="css-transform-origin" class="css-transform-origin" x="1035" y="88" width="105" height="52" style="fill:#f0fdf4;stroke:#16a34a"/>
    <g id="ignored-transform-origin" transform="rotate(10)" transform-origin="left right"><rect x="1160" y="130" width="10" height="10" fill="none" stroke="none"/></g>
    <rect id="media-rule" class="media-rule" x="1160" y="88" width="70" height="52"/>
    <switch>
      <rect id="switch-unsupported" requiredExtensions="https://example.test/ext" x="1160" y="155" width="70" height="40" fill="#dc2626"/>
      <rect id="switch-fallback" x="1160" y="155" width="70" height="40" fill="#16a34a" stroke="#14532d"/>
      <rect id="switch-skipped" x="1160" y="155" width="70" height="40" fill="#2563eb"/>
    </switch>
    <rect id="alpha-shape" x="580" y="615" width="120" height="50" style="fill:rgba(239,68,68,0.5);stroke:#2563ebcc;stroke-width:6;fill-opacity:0.8;stroke-opacity:0.5"/>
    <line id="dash-line" x1="120" y1="650" x2="300" y2="650" style="stroke:#0f766e;stroke-width:8;stroke-dasharray:18 10;stroke-dashoffset:5;stroke-linecap:round;stroke-linejoin:bevel"/>
    <line id="path-length-line" x1="120" y1="675" x2="220" y2="675" pathLength="50" style="stroke:#0891b2;stroke-width:4;stroke-dasharray:10 5"/>
    <path id="ignored-path-length" d="M 120 700 H 220" pathLength="100" fill="none" stroke="#64748b"/>
    <line id="negative-stroke-width" x1="230" y1="675" x2="300" y2="675" style="stroke:#7f1d1d;stroke-width:-2"/>
    <rect id="ignored-vector-effect" x="305" y="668" width="10" height="10" fill="#f8fafc" stroke="none" vector-effect="non-scaling-size"/>
    <g id="scaled-stroke-group" transform="translate(320 640) scale(2)" stroke-linejoin="arcs">
      <line id="scaled-stroke" x1="0" y1="0" x2="50" y2="0" style="stroke:#7c3aed;stroke-width:3;stroke-dasharray:9 3"/>
      <line id="non-scaling-stroke" x1="0" y1="18" x2="50" y2="18" style="stroke:#be185d;stroke-width:3;stroke-dasharray:9 3;vector-effect:non-scaling-stroke"/>
      <text id="scaled-text" x="62" y="10" style="font-size:12;font-family:Arial;fill:#111827;stroke:#ffffff;stroke-width:1;vector-effect:non-scaling-stroke">Scale</text>
    </g>
    <g id="ignored-stroke-enum" stroke-linecap="triangle"><line x1="450" y1="675" x2="520" y2="675" stroke="none"/></g>
    <text id="rich-text" x="330" y="660" rotate="6" style="font-size:24;font-family:Arial;fill:#111827;font-variant:small-caps;text-transform:capitalize">rich <tspan style="fill:#dc2626;font-weight:700;baseline-shift:super;text-transform:uppercase">red</tspan><tspan style="fill:#2563eb;font-style:italic;text-decoration:underline line-through;text-decoration-style:wavy;letter-spacing:2px;text-transform:none"> blue</tspan></text>
    <text id="anchored-text" x="680" y="660" style="font-size:24;font-family:Arial;fill:#0f172a;stroke:#ffffff;stroke-width:1;stroke-opacity:.5;text-anchor:middle;dominant-baseline:middle;text-decoration-line:underline;text-decoration-style:dashed;text-decoration-color:#dc2626;text-decoration-thickness:3px">Centered</text>
    <text id="decoration-inherit" x="560" y="700" style="font-size:18;font-family:Arial;fill:#0f172a;text-decoration-line:underline;text-decoration-style:wavy;text-decoration-color:#dc2626;text-decoration-thickness:2px">Inherited <tspan style="text-decoration-style:inherit;text-decoration-color:inherit;text-decoration-thickness:inherit">decor</tspan></text>
    <text id="preserve-text" x="90" y="355" xml:space="preserve" style="font-size:22;font-family:Arial;fill:#64748b">  padded  <tspan style="fill:#0f766e"> kept </tspan></text>
    <text id="length-text" x="735" y="95" textLength="170" lengthAdjust="spacing" style="font-size:22;font-family:Arial;fill:#334155">Wide gap</text>
    <text id="length-glyphs-text" x="735" y="125" textLength="170" lengthAdjust=" SPACINGANDGLYPHS " style="font-size:22;font-family:Arial;fill:#334155;letter-spacing:NORMAL">Glyph fit</text>
    <text id="word-spacing-text" x="735" y="155" word-spacing="8px" style="font-size:22;font-family:Arial;fill:#334155">Wide gap</text>
    <g id="inherited-word-spacing" word-spacing="8px"><text x="735" y="185" style="font-size:22;font-family:Arial;fill:#334155">Inherited gap</text></g>
    <g id="hidden-text-layout" word-spacing="8px"><text x="735" y="215" fill="none" stroke="none">Hidden gap</text></g>
    <text id="font-shorthand" class="font-short-title" x="760" y="135">Font short</text>
    <text id="rtl-text" x="560" y="95" direction="rtl" style="font-size:22;font-family:Arial;fill:#0f766e">RTL
line</text>
    <text class="css-positioned-text" style="font-size:18;font-family:Arial;fill:#1d4ed8">CSS text position</text>
    <text id="tspan-position" style="font-size:18;font-family:Arial;fill:#334155"><tspan x="900" y="455" dx="10" dy="5">From tspan</tspan><tspan x="900" dy="28">Next line</tspan></text>
    <text id="first-tspan-baseline" style="font-size:18;font-family:Arial;fill:#0f766e"><tspan x="900" y="500" dominant-baseline="middle">Tspan base</tspan></text>
    <text id="unsupported-tspan-anchor" x="900" y="535" style="font-size:18;font-family:Arial;fill:#991b1b">Lead<tspan x="950" y="535" text-anchor="middle">Chunk</tspan></text>
    <g class="relative-font" fill="#111827" font-family="Arial">
      <text class="em-text" x="560" y="135">Em</text>
      <text class="calc-text" x="640" y="135">Calc</text>
    </g>
    <rect id="gradient-fill" x="900" y="615" width="120" height="50" style="fill:url(#linear-fallback);stroke:url(#radial-fallback)"/>
    <rect id="empty-gradient-fill" x="1030" y="615" width="40" height="50" style="fill:url(#empty-gradient)"/>
    <rect id="missing-base-gradient-fill" x="1075" y="615" width="40" height="50" style="fill:url(#missing-base-gradient)"/>
    <circle id="pattern-fill" cx="1080" cy="640" r="32" style="fill:url(#pattern-fallback);stroke:#334155"/>
    <g id="group-clipped-shapes" clip-path="url(#group-clip)">
      <rect x="1130" y="615" width="90" height="50" fill="#fef9c3" stroke="#a16207"/>
      <line x1="1130" y1="665" x2="1220" y2="615" stroke="#92400e" stroke-width="5"/>
    </g>
    <polygon id="unsupported-clip-target" points="1120,690 1160,690 1140,715" clip-path="url(#group-clip)" fill="#fecaca" stroke="#991b1b"/>
    <use href="#reused-chip" class="accent-use" x="360" y="400"/>
    <use id="ignored-filtered-use" href="#hidden-filtered-use-target" x="540" y="600"/>
    <use id="symbol-viewbox-use" class="css-use-frame" href="#viewbox-icon" preserveAspectRatio="xMaxYMax slice"/>
    <use id="context-paint-use" href="#context-badge" x="455" y="600" width="80" height="40" fill="#123456" stroke="#abcdef"/>
    <svg id="nested-viewbox" class="css-nested-frame" viewBox="0 0 20 10" preserveAspectRatio="none">
      <rect x="50%" y="50%" width="25%" height="50%" fill="#0f766e" stroke="#064e3b" stroke-width="1"/>
    </svg>
    <svg id="nested-overflow" class="css-overflow-frame" viewBox="0 0 20 10" overflow="hidden">
      <rect id="nested-overflow-rect" x="-5" y="-5" width="30" height="20" fill="#fee2e2" stroke="#991b1b" stroke-width="1"/>
    </svg>
    <svg id="visible-overflow" x="1205" y="610" width="40" height="40" viewBox="0 0 20 10" overflow="visible"><rect x="-5" y="-5" width="30" height="20" fill="#f8fafc" stroke="#64748b"/></svg>
    <svg id="hidden-overflow-empty" x="1205" y="660" width="40" height="30" viewBox="0 0 20 10" overflow="hidden"><rect x="-5" y="-5" width="30" height="20" opacity="0" fill="#111827"/></svg>
    <g transform="translate(90 390) scale(1.5)">
      <rect id="scaled" width="160" height="80" style="fill:#dbeafe;stroke:#2563eb"/>
    </g>
  </g>
</svg>`;

const state: {
  tab: string;
  svgraph: SVGraphDocument | null;
  presentation: SVGraphPresentationProjection | null;
  webgpu: boolean;
  undoStack: string[];
  redoStack: string[];
  lastSourceValue: string;
  storageStatus: string;
  assistantBackendPolicy: AssistantBackendPolicy;
  assistantStatus: string;
  assistantRawOutput: string;
  assistantProposal: AssistantPatchProposal | null;
  assistantProposalSource: string;
  assistantWorker: Worker | null;
} = {
  tab: "summary",
  svgraph: null,
  presentation: null,
  webgpu: false,
  undoStack: [],
  redoStack: [],
  lastSourceValue: "",
  storageStatus: "Storage idle",
  assistantBackendPolicy: "webgpu",
  assistantStatus: "Local LLM idle",
  assistantRawOutput: "",
  assistantProposal: null,
  assistantProposalSource: "",
  assistantWorker: null,
};

let source: HTMLTextAreaElement;
let preview: HTMLElement;
let panel: HTMLElement;
let fileInput: HTMLInputElement;
let undoButton: HTMLButtonElement;
let redoButton: HTMLButtonElement;
let clearSavedButton: HTMLButtonElement;
const documentDbName = "svgraph-documents";
const documentStoreName = "documents";
const activeDocumentKey = "active-svg";

function mustElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (!element) throw new Error(`missing #${id}`);
  return element as T;
}

function setSourceValue(value: string, options: { record: boolean; persist?: boolean } = { record: true, persist: true }): void {
  if (options.record && source.value !== value) {
    state.undoStack.push(source.value);
    state.redoStack = [];
  }
  source.value = value;
  state.lastSourceValue = value;
  updateHistoryButtons();
  render();
  if (options.persist !== false) void persistSourceDocument(value);
}

function recordManualSourceEdit(): void {
  if (source.value === state.lastSourceValue) return;
  state.undoStack.push(state.lastSourceValue);
  state.redoStack = [];
  state.lastSourceValue = source.value;
  updateHistoryButtons();
  render();
  void persistSourceDocument(source.value);
}

function undoSourceEdit(): void {
  const previous = state.undoStack.pop();
  if (previous == null) return;
  state.redoStack.push(source.value);
  source.value = previous;
  state.lastSourceValue = previous;
  updateHistoryButtons();
  render();
  void persistSourceDocument(previous);
}

function redoSourceEdit(): void {
  const next = state.redoStack.pop();
  if (next == null) return;
  state.undoStack.push(source.value);
  source.value = next;
  state.lastSourceValue = next;
  updateHistoryButtons();
  render();
  void persistSourceDocument(next);
}

function updateHistoryButtons(): void {
  undoButton.disabled = state.undoStack.length === 0;
  redoButton.disabled = state.redoStack.length === 0;
}

function setStorageStatus(value: string): void {
  state.storageStatus = value;
  if (state.svgraph) renderPanel();
}

async function persistSourceDocument(value: string): Promise<void> {
  try {
    await saveSourceDocument(value);
    setStorageStatus("Saved active SVG source to IndexedDB");
  } catch (error) {
    setStorageStatus(`Storage save failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function openDocumentDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(documentDbName, 1);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(documentStoreName)) db.createObjectStore(documentStoreName);
    };
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
  });
}

async function saveSourceDocument(value: string): Promise<void> {
  const db = await openDocumentDb();
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(documentStoreName, "readwrite");
    transaction.objectStore(documentStoreName).put(value, activeDocumentKey);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

async function loadSourceDocument(): Promise<string | null> {
  const db = await openDocumentDb();
  const value = await new Promise<string | null>((resolve, reject) => {
    const transaction = db.transaction(documentStoreName, "readonly");
    const request = transaction.objectStore(documentStoreName).get(activeDocumentKey);
    request.onsuccess = () => resolve(typeof request.result === "string" ? request.result : null);
    request.onerror = () => reject(request.error);
  });
  db.close();
  return value;
}

async function clearSavedSourceDocument(): Promise<void> {
  const db = await openDocumentDb();
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(documentStoreName, "readwrite");
    transaction.objectStore(documentStoreName).delete(activeDocumentKey);
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
  });
  db.close();
}

async function clearSavedSourceDocumentWithStatus(): Promise<void> {
  try {
    await clearSavedSourceDocument();
    setStorageStatus("Cleared saved SVG source from IndexedDB");
  } catch (error) {
    setStorageStatus(`Storage clear failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

function localName(node: Element): string {
  return node.localName || node.nodeName.replace(/^.*:/, "");
}

function attrs(element: Element): Record<string, string> {
  return Object.fromEntries(Array.from(element.attributes || []).map((attr) => [attr.name, attr.value]).sort());
}

function hrefValue(element: Element): string {
  return element.getAttribute("href") || element.getAttributeNS("http://www.w3.org/1999/xlink", "href") || element.getAttribute("xlink:href") || "";
}

function hasHrefAttribute(element: Element): boolean {
  return element.hasAttribute("href") || element.hasAttributeNS("http://www.w3.org/1999/xlink", "href") || element.hasAttribute("xlink:href");
}

function dataAttrs(attributes: Record<string, string>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(attributes)
      .filter(([key]) => key.startsWith("data-"))
      .map(([key, value]) => [key.slice(5), value]),
  );
}

function metadata(element: Element): { text?: string; json?: JsonValue } {
  const meta = Array.from(element.children).find((child) => localName(child) === "metadata");
  if (!meta) return {};
  const text = (meta.textContent || "").trim();
  if (!text) return {};
  try {
    return { text, json: JSON.parse(text) as JsonValue };
  } catch (_) {
    return { text };
  }
}

function dependencies(element: Element, attributes: Record<string, string>): Dependency[] {
  const id = attributes.id || localName(element);
  const deps: Dependency[] = [];
  for (const [name, value] of Object.entries(attributes)) {
    if ((name === "href" || name.endsWith(":href")) && value) {
      deps.push({ kind: "href", source: id, target: value, attribute: "href" });
    }
    for (const match of value.matchAll(/url\(\s*['"]?(#[^)'" ]+)['"]?\s*\)/g)) {
      deps.push({ kind: "paint-server", source: id, target: match[1] || "", attribute: name });
    }
  }
  return deps;
}

function nodeToSVGraph(element: Element, nodeId: string): SVGraphNode {
  const attributes = attrs(element);
  const children = Array.from(element.children)
    .filter((child) => localName(child) !== "metadata")
    .map((child, index) => nodeToSVGraph(child, `${nodeId}.${index}`));
  const text = Array.from(element.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => (node.textContent || "").trim())
    .filter(Boolean)
    .join(" ");
  return {
    node_id: nodeId,
    tag: localName(element),
    attributes,
    data: dataAttrs(attributes),
    metadata: metadata(element),
    dependencies: dependencies(element, attributes),
    children,
    text: text || null,
  };
}

function flatten(node: SVGraphNode): SVGraphNode[] {
  return [node, ...node.children.flatMap(flatten)];
}

function viewBox(node: SVGraphNode): [number, number, number, number] {
  const raw = node.attributes.viewBox;
  if (raw) {
    const values = raw.replaceAll(",", " ").split(/\s+/).map(Number).filter((value) => Number.isFinite(value));
    if (values.length === 4 && values[0] !== undefined && values[1] !== undefined && values[2] !== undefined && values[3] !== undefined) {
      return [values[0], values[1], values[2], values[3]];
    }
  }
  return [0, 0, Number(node.attributes.width) || 0, Number(node.attributes.height) || 0];
}

function nodeTitle(node: SVGraphNode): string | null {
  if (node.data.title) return node.data.title;
  const meta = asObject(node.metadata.json);
  if (typeof meta.title === "string") return meta.title;
  const titleNode = node.children.find((child) => child.tag === "title");
  return titleNode?.text || null;
}

function isSlide(node: SVGraphNode): boolean {
  return node.data.kind === "slide" || node.data.role === "slide" || Object.hasOwn(node.data, "slide");
}

function buildSVGraphPresentation(root: SVGraphNode): SVGraphPresentationProjection {
  const nodes = flatten(root);
  const slides = nodes.filter(isSlide);
  const selectedSlides = slides.length ? slides : [root];
  const rootMeta = asObject(asObject(root.metadata.json).presentation);
  const rootBox = viewBox(root);
  const metaSlideSize = asObject(rootMeta.slideSize || rootMeta.slide_size);
  const slideSize: [number, number] =
    typeof metaSlideSize.width === "number" && typeof metaSlideSize.height === "number"
      ? [metaSlideSize.width, metaSlideSize.height]
      : [rootBox[2] || 960, rootBox[3] || 540];
  const slideItems = selectedSlides.map((node, index) => ({
    slide_id: node.attributes.id || node.data.slide || `slide-${index + 1}`,
    node_id: node.node_id,
    title: nodeTitle(node),
    view_box: viewBox(node),
    data: node.data,
    metadata: node.metadata,
  }));
  const masters = templates(nodes, rootMeta.masters ?? null, "slide-master");
  const layouts = templates(nodes, rootMeta.layouts ?? null, "slide-layout");
  const masterParts = (masters.length ? masters : [null]).map((master, index) => ({
    part_name: `/ppt/slideMasters/slideMaster${index + 1}.xml`,
    content_type: "application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml",
    kind: "slide-master",
    source_node_id: master?.node_id ?? null,
  }));
  const layoutParts = (layouts.length ? layouts : [null]).map((layout, index) => ({
    part_name: `/ppt/slideLayouts/slideLayout${index + 1}.xml`,
    content_type: "application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml",
    kind: "slide-layout",
    source_node_id: layout?.node_id ?? null,
  }));
  return {
    kind: "svgraph-presentation",
    slide_size: slideSize,
    slides: slideItems,
    parts: [
      {
        part_name: "/ppt/presentation.xml",
        content_type: "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml",
        kind: "presentation",
        source_node_id: null,
      },
      ...masterParts,
      ...layoutParts,
      {
        part_name: "/ppt/theme/theme1.xml",
        content_type: "application/vnd.openxmlformats-officedocument.theme+xml",
        kind: "theme",
        source_node_id: null,
      },
      {
        part_name: "/customXml/item1.xml",
        content_type: "application/xml",
        kind: "custom-xml",
        source_node_id: null,
      },
      ...slideItems.map((slide, index) => ({
        part_name: `/ppt/slides/slide${index + 1}.xml`,
        content_type: "application/vnd.openxmlformats-officedocument.presentationml.slide+xml",
        kind: "slide",
        source_node_id: slide.node_id,
      })),
    ],
    masters,
    layouts,
    guides: guides(nodes, rootMeta.guides ?? null),
    rulers: rulers(nodes, rootMeta.rulers ?? null),
    text_styles: textStyles(nodes, rootMeta.textStyles || rootMeta.text_styles || null),
    metadata: rootMeta,
  };
}

function templates(nodes: SVGraphNode[], metadataItems: JsonValue, kind: string): TemplateRecord[] {
  const items = Array.isArray(metadataItems) ? metadataItems : [];
  const fromMeta = items.map((item, index) => {
    const obj = asObject(item);
    return {
      template_id: String(obj.id || obj.name || `${kind}-${index + 1}`),
      kind,
      node_id: null,
      data: {},
      metadata: item,
    };
  });
  const fromNodes = nodes
    .filter((node) => node.data.kind === kind || node.data.role === kind)
    .map((node) => ({
      template_id: node.attributes.id || node.data.template || node.node_id,
      kind,
      node_id: node.node_id,
      data: node.data,
      metadata: node.metadata.json || node.metadata.text || null,
    }));
  return [...fromMeta, ...fromNodes];
}

function guides(nodes: SVGraphNode[], metadataItems: JsonValue): GuideRecord[] {
  const items = Array.isArray(metadataItems) ? metadataItems : [];
  const fromMeta = items.map((item, index) => {
    const obj = asObject(item);
    return {
      guide_id: String(obj.id || `guide-${index + 1}`),
      orientation: String(obj.orientation || "vertical"),
      position: Number(obj.position || 0),
      unit: String(obj.unit || "px"),
      node_id: null,
    };
  });
  const fromNodes = nodes
    .filter((node) => node.data.kind === "guide" || node.data.role === "guide")
    .map((node) => ({
      guide_id: node.attributes.id || node.node_id,
      orientation: node.data.orientation || (node.attributes.y ? "horizontal" : "vertical"),
      position: Number(node.data.position || node.attributes.x || node.attributes.y || 0),
      unit: node.data.unit || "px",
      node_id: node.node_id,
    }));
  return [...fromMeta, ...fromNodes];
}

function rulers(nodes: SVGraphNode[], metadataItems: JsonValue): RulerRecord[] {
  const items = Array.isArray(metadataItems) ? metadataItems : [];
  const fromMeta = items.map((item, index) => {
    const obj = asObject(item);
    return {
      ruler_id: String(obj.id || `ruler-${index + 1}`),
      orientation: String(obj.orientation || "horizontal"),
      origin: Number(obj.origin || 0),
      unit: String(obj.unit || "px"),
      spacing: obj.spacing == null ? null : Number(obj.spacing),
      node_id: null,
    };
  });
  const fromNodes = nodes
    .filter((node) => node.data.kind === "ruler" || node.data.role === "ruler")
    .map((node) => ({
      ruler_id: node.attributes.id || node.node_id,
      orientation: node.data.orientation || "horizontal",
      origin: Number(node.data.origin || 0),
      unit: node.data.unit || "px",
      spacing: node.data.spacing == null ? null : Number(node.data.spacing),
      node_id: node.node_id,
    }));
  return [...fromMeta, ...fromNodes];
}

function textStyles(nodes: SVGraphNode[], metadataStyles: JsonValue): TextStyleRecord[] {
  const fromMeta = Array.isArray(metadataStyles)
    ? metadataStyles.map((item, index) => {
        const obj = asObject(item);
        const role = String(obj.role || obj.id || `text-style-${index + 1}`);
        return {
          style_id: String(obj.id || role),
          role,
          properties: obj,
          node_id: null,
        };
      })
    : Object.entries(asObject(metadataStyles)).map(([role, properties]) => ({
        style_id: role,
        role,
        properties: asObject(properties),
        node_id: null,
      }));
  const fromNodes = nodes
    .filter((node) => node.data.kind === "style-template" || node.data.role === "style-template")
    .map((node) => ({
      style_id: node.attributes.id || node.data.style || node.node_id,
      role: node.data.role || node.data.style || node.attributes.id || node.node_id,
      properties: { ...node.attributes, ...node.data },
      node_id: node.node_id,
    }));
  return [...fromMeta, ...fromNodes];
}

export function buildSVGraph(svgText: string): SVGraphDocument {
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgText, "image/svg+xml");
  const error = doc.querySelector("parsererror");
  if (error) throw new Error((error.textContent || "").trim());
  const root = nodeToSVGraph(doc.documentElement, "n0");
  const dependencies = flatten(root).flatMap((node) => node.dependencies);
  const presentation = buildSVGraphPresentation(root);
  const coverage = analyzeSvgCoverage(doc.documentElement);
  return {
    kind: "svgraph",
    version: "0.3-svgraph-web-ts",
    root,
    metadata: root.metadata,
    dependencies,
    coverage,
    presentation,
  };
}

export function buildSVGraphSidecar(svgraph: SVGraphDocument, svgText = ""): SVGraphSidecar {
  return {
    kind: "svgraph-sidecar",
    version: svgraph.version,
    source_svg: svgText,
    metadata: svgraph.metadata,
    dependencies: svgraph.dependencies,
    coverage: svgraph.coverage,
    presentation: svgraph.presentation,
  };
}

export function buildOfficeCausalPayload(svgraph: SVGraphDocument): OfficeCausalPayload {
  const nodes = flatten(svgraph.root);
  const idByNode = new Map(nodes.map((node) => [node.node_id, officeCausalDataId(node)]));
  const bySvgId = new Map(nodes.flatMap((node) => (node.attributes.id ? [[node.attributes.id, node] as const] : [])));
  const partByNodeId = slideMembership(svgraph);
  const causalNodes = nodes.map((node) => officeCausalNode(node, partByNodeId.get(node.node_id) ?? null, idByNode.get(node.node_id)!));
  const edges: OfficeCausalEdge[] = [];
  for (const node of nodes) {
    for (const child of node.children) {
      edges.push(officeCausalEdge("contains", idByNode.get(node.node_id)!, idByNode.get(child.node_id)!));
    }
    for (const dependency of node.dependencies) {
      const target = dependency.target.startsWith("#") ? bySvgId.get(dependency.target.slice(1)) : null;
      if (target) edges.push(officeCausalEdge("references", idByNode.get(node.node_id)!, idByNode.get(target.node_id)!, dependency.kind));
    }
    if (isOfficeCausalRelationNode(node)) {
      edges.push(...officeCausalRelationEdges(node, idByNode, bySvgId));
    }
    if (node.text) {
      const semanticParent = nearestSemanticAncestor(node, nodes);
      if (semanticParent && semanticParent.node_id !== node.node_id) {
        edges.push(officeCausalEdge("mentions", idByNode.get(semanticParent.node_id)!, idByNode.get(node.node_id)!, "text"));
      }
    }
  }
  return {
    version: 1,
    generator: "office-causal",
    nodes: causalNodes,
    edges: uniqueOfficeCausalEdges(edges),
    analysis: {
      svgraph: {
        version: svgraph.version,
        coverage: svgraph.coverage,
        presentation: svgraph.presentation,
      },
    },
  };
}

export function buildOfficeCausalJsonl(svgraph: SVGraphDocument): string {
  const payload = buildOfficeCausalPayload(svgraph);
  return [
    JSON.stringify({ t: "meta", version: payload.version, generator: payload.generator }),
    JSON.stringify({ t: "analysis", analysis: payload.analysis }),
    ...payload.nodes.map((node) => JSON.stringify({ t: "node", ...node })),
    ...payload.edges.map((edge) => JSON.stringify({ t: "edge", ...edge })),
  ].join("\n") + "\n";
}

function officeCausalDataId(node: SVGraphNode): `ocz1:${string}` {
  const stable = node.attributes.id || node.node_id;
  return `ocz1:svgraph-${stable.replace(/[^A-Za-z0-9_.:-]+/g, "-")}` as `ocz1:${string}`;
}

function officeCausalNode(node: SVGraphNode, part: string | null, id: `ocz1:${string}`): OfficeCausalNode {
  const bbox = nodeBBox(node);
  return {
    id,
    kind: officeCausalNodeKind(node),
    part: part ?? "svgraph/source.svg",
    path: `${node.tag}[${node.node_id}]`,
    ...(nodeLabel(node) ? { label: nodeLabel(node)! } : {}),
    ...(node.text ? { text: node.text } : {}),
    ...(bbox ? { bbox } : {}),
    tags: officeCausalTags(node),
  };
}

function officeCausalNodeKind(node: SVGraphNode): OfficeCausalNode["kind"] {
  const kind = node.data.kind || node.data.role;
  if (kind === "slide") return "slide";
  if (kind === "table" || kind === "cell") return "table";
  if (kind === "entity" || kind === "service" || kind === "database" || kind === "actor") return "entity";
  if (kind === "claim" || kind === "annotation") return "claim";
  if (node.tag === "svg") return "document";
  if (node.tag === "image") return "image";
  return "shape";
}

function officeCausalTags(node: SVGraphNode): string[] {
  return [...new Set([node.tag, node.data.kind, node.data.role, node.data.group].filter((value): value is string => !!value))];
}

function nodeLabel(node: SVGraphNode): string | null {
  return node.data.title || node.data.label || node.attributes["aria-label"] || node.attributes.id || node.text || null;
}

function nodeBBox(node: SVGraphNode): OfficeCausalNode["bbox"] | null {
  const x = Number(node.attributes.x ?? node.attributes.cx ?? node.attributes.x1 ?? 0);
  const y = Number(node.attributes.y ?? node.attributes.cy ?? node.attributes.y1 ?? 0);
  const width = Number(node.attributes.width ?? node.attributes.r ?? node.attributes.rx ?? 0);
  const height = Number(node.attributes.height ?? node.attributes.r ?? node.attributes.ry ?? 0);
  if (![x, y, width, height].every(Number.isFinite) || (width === 0 && height === 0)) return null;
  const isCenter = node.attributes.cx != null || node.attributes.cy != null;
  return { x: isCenter ? x - width : x, y: isCenter ? y - height : y, w: isCenter ? width * 2 : width, h: isCenter ? height * 2 : height, unit: "px" };
}

function officeCausalEdge(kind: OfficeCausalEdge["kind"], from: `ocz1:${string}`, to: `ocz1:${string}`, reason = ""): OfficeCausalEdge {
  return { id: `${kind}:${from}->${to}${reason ? `#${reason}` : ""}`, kind, from, to };
}

function isOfficeCausalRelationNode(node: SVGraphNode): boolean {
  return (
    node.data.kind === "relation" ||
    node.data.role === "relation" ||
    node.data.kind === "causal" ||
    node.data.edge === "causes" ||
    node.data.type === "causes"
  );
}

function officeCausalRelationEdges(
  node: SVGraphNode,
  idByNode: Map<string, `ocz1:${string}`>,
  bySvgId: Map<string, SVGraphNode>,
): OfficeCausalEdge[] {
  const relationId = idByNode.get(node.node_id)!;
  const bind = node.data.bind || node.data.relation || "";
  const from = node.data.from || bind.split(/->|→/)[0]?.trim();
  const to = node.data.to || bind.split(/->|→/)[1]?.trim();
  const source = from ? bySvgId.get(from.replace(/^#/, "")) : null;
  const target = to ? bySvgId.get(to.replace(/^#/, "")) : null;
  const edges: OfficeCausalEdge[] = [];
  if (source) edges.push(officeCausalEdge("references", relationId, idByNode.get(source.node_id)!, "relation-from"));
  if (target) edges.push(officeCausalEdge("references", relationId, idByNode.get(target.node_id)!, "relation-to"));
  if (source && target && (node.data.edge === "causes" || node.data.kind === "causal" || node.data.type === "causes")) {
    edges.push({
      ...officeCausalEdge("causes", idByNode.get(source.node_id)!, idByNode.get(target.node_id)!, "svgraph-relation"),
      causal: {
        polarity: node.data.polarity === "-" ? "-" : node.data.polarity === "+" ? "+" : "?",
        mechanism: node.data.mechanism || node.text || "SVGraph semantic relation",
        confidence: Number(node.data.confidence) || 0.5,
        evidence: [{ nodeId: relationId, quote: node.text || nodeLabel(node) || "relation" }],
        status: "hypothesis",
      },
    });
  }
  return edges;
}

function uniqueOfficeCausalEdges(edges: OfficeCausalEdge[]): OfficeCausalEdge[] {
  return [...new Map(edges.map((edge) => [edge.id, edge])).values()];
}

function slideMembership(svgraph: SVGraphDocument): Map<string, string> {
  const map = new Map<string, string>();
  const slideRoots = new Map(svgraph.presentation.slides.map((slide, index) => [slide.node_id, `ppt/slides/slide${index + 1}.xml`]));
  const visit = (node: SVGraphNode, current: string | null) => {
    const next = slideRoots.get(node.node_id) ?? current;
    if (next) map.set(node.node_id, next);
    node.children.forEach((child) => visit(child, next));
  };
  visit(svgraph.root, null);
  return map;
}

function nearestSemanticAncestor(node: SVGraphNode, nodes: SVGraphNode[]): SVGraphNode | null {
  const parts = node.node_id.split(".");
  while (parts.length > 1) {
    parts.pop();
    const candidate = nodes.find((item) => item.node_id === parts.join("."));
    if (candidate && Object.keys(candidate.data).length > 0) return candidate;
  }
  return null;
}

export function assistantPatchProposal(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): AssistantPatchProposal {
  const semanticNodeIds = new Set(flatten(svgraph.root).filter((node) => Object.keys(node.data).length > 0).map((node) => node.node_id));
  const ops = presentation.slides
    .filter((slide) => !semanticNodeIds.has(slide.node_id))
    .slice(0, 3)
    .map((slide) => ({
      op: "mark-slide",
      node_id: slide.node_id,
      title: slide.title || slide.slide_id,
    }));
  return {
    summary: ops.length ? "Detected slide candidates that can be reviewed before applying." : "No assistant patch is needed for the current SVGraph.",
    ops,
    confidence: ops.length ? 0.72 : 1,
  };
}

export function buildSVGraphAssistantPrompt(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): string {
  const nodes = flatten(svgraph.root)
    .filter((node) => node.tag !== "metadata")
    .slice(0, 80)
    .map((node) => ({
      node_id: node.node_id,
      tag: node.tag,
      id: node.attributes.id ?? null,
      data: node.data,
      text: node.text,
      child_count: node.children.length,
    }));
  return JSON.stringify({
    task: "suggest-svgraph-patch",
    instructions: [
      "Return only JSON.",
      "Suggest conservative SVGraph patch operations for slide, table, relation, reading-order, or metadata semantics.",
      "Do not invent node_id values; use only provided nodes.",
      "Allowed ops are mark-slide, set-data, set-metadata, mark-table, mark-cell, bind-relation, and set-reading-order.",
    ],
    output_schema: {
      summary: "string",
      confidence: "number from 0 to 1",
      ops: [{ op: "allowed op", node_id: "existing node_id" }],
    },
    slide_size: presentation.slide_size,
    slides: presentation.slides,
    dependencies: svgraph.dependencies.slice(0, 80),
    coverage: svgraph.coverage,
    nodes,
  }, null, 2);
}

export function parseAssistantPatchProposal(value: unknown): AssistantPatchProposal {
  const payload = typeof value === "string" ? JSON.parse(extractJsonObject(value)) : value;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) throw new Error("assistant output must be a JSON object");
  const object = payload as Record<string, unknown>;
  const summary = typeof object.summary === "string" ? object.summary : "";
  const confidence = typeof object.confidence === "number" ? object.confidence : 0;
  const rawOps = Array.isArray(object.ops) ? object.ops : [];
  const ops = rawOps.map((item) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) return { op: "", node_id: "" };
    const op = item as Record<string, unknown>;
    const result: AssistantPatchOp = {
      op: typeof op.op === "string" ? op.op : "",
      node_id: typeof op.node_id === "string" ? op.node_id : "",
    };
    for (const [key, itemValue] of Object.entries(op)) {
      if (key === "op" || key === "node_id") continue;
      if (isJsonValue(itemValue)) result[key] = itemValue;
    }
    return result;
  });
  return { summary, confidence, ops };
}

function extractJsonObject(value: string): string {
  const start = value.indexOf("{");
  const end = value.lastIndexOf("}");
  if (start < 0 || end < start) throw new Error("assistant output did not contain a JSON object");
  return value.slice(start, end + 1);
}

function isJsonValue(value: unknown): value is JsonValue {
  if (value == null || typeof value === "boolean" || typeof value === "number" || typeof value === "string") return true;
  if (Array.isArray(value)) return value.every(isJsonValue);
  return typeof value === "object" && Object.values(value as Record<string, unknown>).every(isJsonValue);
}

function deterministicAssistantProposal(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): AssistantPatchProposal {
  return assistantPatchProposal(svgraph, presentation);
}

function activeAssistantProposal(svgraph: SVGraphDocument, presentation: SVGraphPresentationProjection): AssistantPatchProposal {
  return state.assistantProposal && state.assistantProposalSource === source.value ? state.assistantProposal : deterministicAssistantProposal(svgraph, presentation);
}

function createAssistantWorker(): Worker {
  const code = `
    let generator = null;
    let loadedKey = "";
    const modelId = ${JSON.stringify(assistantModelId)};
    function postStatus(status) {
      self.postMessage({ type: "status", status });
    }
    async function loadGenerator(policy) {
      const key = policy + ":" + modelId;
      if (generator && loadedKey === key) return generator;
      postStatus("Loading Transformers.js runtime");
      const mod = await import("https://cdn.jsdelivr.net/npm/@huggingface/transformers");
      postStatus("Loading local model " + modelId);
      generator = await mod.pipeline("text-generation", modelId, {
        device: policy === "webgpu" ? "webgpu" : "wasm",
        dtype: policy === "webgpu" ? "q4" : "q8",
      });
      loadedKey = key;
      return generator;
    }
    self.onmessage = async (event) => {
      const message = event.data || {};
      if (message.type !== "generate") return;
      try {
        if (message.policy === "disabled") {
          self.postMessage({ type: "error", error: "Local LLM is disabled" });
          return;
        }
        const run = await loadGenerator(message.policy);
        postStatus("Generating SVGraph patch proposal");
        const output = await run(message.prompt, {
          max_new_tokens: 512,
          temperature: 0.2,
          do_sample: false,
          return_full_text: false,
        });
        const first = Array.isArray(output) ? output[0] : output;
        const raw = typeof first === "string" ? first : String(first?.generated_text || first?.text || JSON.stringify(first));
        self.postMessage({ type: "proposal", raw, proposal: JSON.parse(raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1)) });
      } catch (error) {
        self.postMessage({ type: "error", error: error && error.message ? error.message : String(error) });
      }
    };
  `;
  return new Worker(URL.createObjectURL(new Blob([code], { type: "text/javascript" })), { type: "module" });
}

async function requestAssistantPatch(policy: AssistantBackendPolicy): Promise<void> {
  if (!state.svgraph || !state.presentation) return;
  if (policy === "disabled") {
    state.assistantStatus = "Local LLM disabled; deterministic proposal is active";
    state.assistantProposal = null;
    state.assistantRawOutput = "";
    renderPanel();
    return;
  }
  if (typeof Worker === "undefined") {
    state.assistantStatus = "Web Worker unavailable; deterministic proposal is active";
    renderPanel();
    return;
  }
  state.assistantBackendPolicy = policy;
  state.assistantStatus = "Preparing local LLM worker";
  state.assistantRawOutput = "";
  renderPanel();
  const prompt = buildSVGraphAssistantPrompt(state.svgraph, state.presentation);
  const worker = state.assistantWorker ?? createAssistantWorker();
  state.assistantWorker = worker;
  worker.onmessage = (event: MessageEvent<AssistantWorkerEvent>) => {
    const message = event.data;
    if (message.type === "status") {
      state.assistantStatus = message.status;
    } else if (message.type === "proposal") {
      try {
        const proposal = parseAssistantPatchProposal(message.proposal);
        const validation = state.svgraph ? validateAssistantPatch(proposal, state.svgraph) : { status: "rejected", errors: ["missing SVGraph"] };
        if (validation.status !== "accepted") throw new Error(validation.errors.join("; "));
        state.assistantProposal = proposal;
        state.assistantProposalSource = source.value;
        state.assistantRawOutput = message.raw;
        state.assistantStatus = "Local LLM proposal ready for review";
      } catch (error) {
        state.assistantStatus = `Local LLM proposal rejected: ${error instanceof Error ? error.message : String(error)}`;
      }
    } else {
      state.assistantStatus = `Local LLM failed: ${message.error}`;
    }
    renderPanel();
  };
  worker.onerror = (error) => {
    state.assistantStatus = `Local LLM worker error: ${error.message}`;
    renderPanel();
  };
  worker.postMessage({ type: "generate", policy, prompt });
}

export function validateAssistantPatch(proposal: AssistantPatchProposal, svgraph: SVGraphDocument): AssistantPatchValidation {
  const errors: string[] = [];
  const nodeIds = new Set(flatten(svgraph.root).map((node) => node.node_id));
  if (!proposal.summary || typeof proposal.summary !== "string") errors.push("summary must be a non-empty string");
  if (!Number.isFinite(proposal.confidence) || proposal.confidence < 0 || proposal.confidence > 1) errors.push("confidence must be between 0 and 1");
  if (!Array.isArray(proposal.ops)) {
    errors.push("ops must be an array");
  } else {
    proposal.ops.forEach((op, index) => {
      if (!assistantAllowedOpNames.includes(op.op)) errors.push(`ops[${index}].op is not allowed`);
      if (!op.node_id || !nodeIds.has(op.node_id)) errors.push(`ops[${index}].node_id does not reference an SVGraph node`);
      if ((op.op === "set-data" || op.op === "set-metadata") && typeof op.name !== "string") errors.push(`ops[${index}].name must be a string`);
      if (op.op === "bind-relation" && (typeof op.from !== "string" || typeof op.to !== "string")) errors.push(`ops[${index}].from and ops[${index}].to must be strings`);
    });
  }
  return { status: errors.length ? "rejected" : "accepted", errors };
}

export function assistantPatchDiff(proposal: AssistantPatchProposal, svgraph: SVGraphDocument): AssistantPatchDiff[] {
  const nodes = new Map(flatten(svgraph.root).map((node) => [node.node_id, node]));
  return proposal.ops.flatMap((op) => {
    const node = nodes.get(op.node_id);
    if (!node) return [assistantUnsupportedDiff(op, "node")];
    if (op.op === "mark-slide") {
      const rows: AssistantPatchDiff[] = [assistantDataDiff(op, node, "kind", "slide")];
      if (typeof op.title === "string") rows.push(assistantDataDiff(op, node, "title", op.title));
      return rows;
    }
    if (op.op === "mark-table") return [assistantDataDiff(op, node, "kind", "table")];
    if (op.op === "mark-cell") return [assistantDataDiff(op, node, "kind", "cell")];
    if (op.op === "set-data" && typeof op.name === "string") return [assistantDataDiff(op, node, op.name, patchValue(op.value))];
    if (op.op === "set-metadata" && typeof op.name === "string") return [assistantMetadataDiff(op, node, op.name, patchValue(op.value))];
    if (op.op === "bind-relation" && typeof op.from === "string" && typeof op.to === "string") {
      return [assistantDataDiff(op, node, "bind", `${op.from}->${op.to}`)];
    }
    if (op.op === "set-reading-order") return [assistantDataDiff(op, node, "reading-order", patchValue(op.value ?? op.order))];
    return [assistantUnsupportedDiff(op, op.op)];
  });
}

function assistantDataDiff(op: AssistantPatchOp, node: SVGraphNode, name: string, after: JsonValue): AssistantPatchDiff {
  const before = node.data[name] ?? null;
  return {
    op: op.op,
    node_id: op.node_id,
    field: `data-${name}`,
    before,
    after,
    status: before === after ? "unchanged" : "pending",
  };
}

function assistantMetadataDiff(op: AssistantPatchOp, node: SVGraphNode, name: string, after: JsonValue): AssistantPatchDiff {
  const metadata = asObject(node.metadata.json);
  const before = patchValue(metadata[name]);
  return {
    op: op.op,
    node_id: op.node_id,
    field: `metadata.${name}`,
    before,
    after,
    status: JSON.stringify(before) === JSON.stringify(after) ? "unchanged" : "pending",
  };
}

function assistantUnsupportedDiff(op: AssistantPatchOp, field: string): AssistantPatchDiff {
  return {
    op: op.op,
    node_id: op.node_id,
    field,
    before: null,
    after: null,
    status: "unsupported",
  };
}

function patchValue(value: JsonValue | undefined): JsonValue {
  return value === undefined ? null : value;
}

export function applyAssistantPatch(svgText: string, proposal: AssistantPatchProposal, svgraph: SVGraphDocument): string {
  const validation = validateAssistantPatch(proposal, svgraph);
  if (validation.status !== "accepted") throw new Error(validation.errors.join("; "));
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgText, "image/svg+xml");
  const error = doc.querySelector("parsererror");
  if (error) throw new Error((error.textContent || "").trim());
  for (const op of proposal.ops) {
    const element = elementByNodeId(doc.documentElement, op.node_id);
    if (!element) throw new Error(`missing SVGraph node ${op.node_id}`);
    applyAssistantPatchOp(element, op);
  }
  return new XMLSerializer().serializeToString(doc.documentElement);
}

function applyAssistantPatchOp(element: Element, op: AssistantPatchOp): void {
  if (op.op === "mark-slide") {
    setDataAttribute(element, "kind", "slide");
    if (typeof op.title === "string") setDataAttribute(element, "title", op.title);
  } else if (op.op === "mark-table") {
    setDataAttribute(element, "kind", "table");
  } else if (op.op === "mark-cell") {
    setDataAttribute(element, "kind", "cell");
  } else if (op.op === "set-data" && typeof op.name === "string") {
    setDataAttribute(element, op.name, op.value);
  } else if (op.op === "set-metadata" && typeof op.name === "string") {
    setMetadataValue(element, op.name, patchValue(op.value));
  } else if (op.op === "bind-relation" && typeof op.from === "string" && typeof op.to === "string") {
    setDataAttribute(element, "bind", `${op.from}->${op.to}`);
  } else if (op.op === "set-reading-order") {
    setDataAttribute(element, "reading-order", op.value ?? op.order);
  }
}

function elementByNodeId(root: Element, nodeId: string): Element | null {
  if (nodeId === "n0") return root;
  if (!nodeId.startsWith("n0.")) return null;
  let current: Element | null = root;
  for (const rawIndex of nodeId.slice(3).split(".")) {
    const index = Number(rawIndex);
    if (!current || !Number.isInteger(index) || index < 0) return null;
    const children: Element[] = Array.from(current.children).filter((child) => localName(child) !== "metadata");
    current = children[index] ?? null;
  }
  return current;
}

function setDataAttribute(element: Element, name: string, value: JsonValue | undefined): void {
  const attr = `data-${name}`;
  if (value == null) {
    element.removeAttribute(attr);
  } else {
    element.setAttribute(attr, String(value));
  }
}

function setMetadataValue(element: Element, name: string, value: JsonValue): void {
  let meta = Array.from(element.children).find((child) => localName(child) === "metadata");
  if (!meta) {
    meta = element.ownerDocument.createElementNS(element.namespaceURI, "metadata");
    element.insertBefore(meta, element.firstChild);
  }
  let payload: Record<string, JsonValue> = {};
  const text = (meta.textContent || "").trim();
  if (text) {
    try {
      payload = asObject(JSON.parse(text) as JsonValue);
    } catch (_) {
      payload = {};
    }
  }
  if (value == null) {
    delete payload[name];
  } else {
    payload[name] = value;
  }
  meta.textContent = JSON.stringify(payload);
}

export function svgToPptx(svgText: string): Uint8Array {
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgText, "image/svg+xml");
  const error = doc.querySelector("parsererror");
  if (error) throw new Error((error.textContent || "").trim());
  const root = doc.documentElement;
  const svgraph = buildSVGraph(svgText);
  const slides = declaredSlides(root);
  const selectedSlides = slides.length ? slides : [root];
  const slideXmls = selectedSlides.map((slide, index) => buildSlideXml(slide, index + 1));
  return writePptx(slideXmls, svgraph, svgText);
}

export function svgToDrawingMl(svgText: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(svgText, "image/svg+xml");
  const error = doc.querySelector("parsererror");
  if (error) throw new Error((error.textContent || "").trim());
  const root = doc.documentElement;
  const slides = declaredSlides(root);
  return buildDrawingMlFragment((slides.length ? slides : [root])[0]!);
}

export function drawingMlToSvg(drawingMlText: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(drawingMlText, "application/xml");
  const error = doc.querySelector("parsererror");
  if (error) throw new Error((error.textContent || "").trim());
  const items = dmlSvgItems(doc.documentElement);
  const bounds = items.map((item) => item.bounds);
  const minX = Math.min(0, ...bounds.map((box) => box.x));
  const minY = Math.min(0, ...bounds.map((box) => box.y));
  const maxX = Math.max(0, ...bounds.map((box) => box.x + box.width));
  const maxY = Math.max(0, ...bounds.map((box) => box.y + box.height));
  const width = Math.max(1, maxX - minX);
  const height = Math.max(1, maxY - minY);
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${formatNumber(minX)} ${formatNumber(minY)} ${formatNumber(width)} ${formatNumber(height)}">${dmlSvgMarkerDefs(items)}${items.map((item) => item.svg).join("")}</svg>`;
}

type DmlSvgItem = {
  svg: string;
  bounds: Box;
};

function dmlSvgItems(root: Element): DmlSvgItem[] {
  return dmlSvgItemsWalk(root, [1, 0, 0, 1, 0, 0]);
}

function dmlSvgItemsWalk(element: Element, matrix: Matrix): DmlSvgItem[] {
  const tag = localName(element);
  if (tag === "grpSp") {
    const groupMatrix = multiply(matrix, dmlGroupMatrix(element));
    return Array.from(element.children).flatMap((child) => dmlSvgItemsWalk(child, groupMatrix));
  }
  const item = tag === "sp" ? dmlShapeToSvg(element) : tag === "cxnSp" ? dmlConnectorToSvg(element) : tag === "graphicFrame" ? dmlTableFrameToSvg(element) : tag === "pic" ? dmlPictureToSvg(element) : null;
  if (item) return [transformDmlSvgItem(item, matrix)];
  return Array.from(element.children).flatMap((child) => dmlSvgItemsWalk(child, matrix));
}

function transformDmlSvgItem(item: DmlSvgItem, matrix: Matrix): DmlSvgItem {
  if (matrixIsIdentity(matrix)) return item;
  const bounds = transformedBox(matrix, item.bounds.x, item.bounds.y, item.bounds.width, item.bounds.height);
  return {
    bounds,
    svg: `<g transform="${svgMatrix(matrix)}">${item.svg}</g>`,
  };
}

function dmlSvgMarkerDefs(items: DmlSvgItem[]): string {
  if (!items.some((item) => item.svg.includes("url(#svgraph-arrow)"))) return "";
  return '<defs><marker id="svgraph-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="context-stroke"/></marker></defs>';
}

function dmlGroupMatrix(element: Element): Matrix {
  const xfrm = childByLocal(childByLocal(element, "grpSpPr"), "xfrm");
  if (!xfrm) return [1, 0, 0, 1, 0, 0];
  const off = childByLocal(xfrm, "off");
  const ext = childByLocal(xfrm, "ext");
  const chOff = childByLocal(xfrm, "chOff");
  const chExt = childByLocal(xfrm, "chExt");
  const x = emuToPx(off?.getAttribute("x"));
  const y = emuToPx(off?.getAttribute("y"));
  const width = emuToPx(ext?.getAttribute("cx"));
  const height = emuToPx(ext?.getAttribute("cy"));
  const childX = emuToPx(chOff?.getAttribute("x"));
  const childY = emuToPx(chOff?.getAttribute("y"));
  const childWidth = chExt ? emuToPx(chExt.getAttribute("cx")) : width;
  const childHeight = chExt ? emuToPx(chExt.getAttribute("cy")) : height;
  const scaleX = childWidth ? width / childWidth : 1;
  const scaleY = childHeight ? height / childHeight : 1;
  let matrix: Matrix = [scaleX, 0, 0, scaleY, x - childX * scaleX, y - childY * scaleY];
  if (childByLocal(element, "grpSpPr") && dmlBool(xfrm.getAttribute("flipH"))) {
    matrix = multiply([-1, 0, 0, 1, x * 2 + width, 0], matrix);
  }
  if (childByLocal(element, "grpSpPr") && dmlBool(xfrm.getAttribute("flipV"))) {
    matrix = multiply([1, 0, 0, -1, 0, y * 2 + height], matrix);
  }
  const rotation = Number(xfrm.getAttribute("rot"));
  if (Number.isFinite(rotation) && rotation) {
    const radians = (rotation / 60000 / 180) * Math.PI;
    const centerX = x + width / 2;
    const centerY = y + height / 2;
    matrix = multiply(multiply([1, 0, 0, 1, centerX, centerY], [Math.cos(radians), Math.sin(radians), -Math.sin(radians), Math.cos(radians), 0, 0]), multiply([1, 0, 0, 1, -centerX, -centerY], matrix));
  }
  return matrix;
}

function matrixIsIdentity(matrix: Matrix): boolean {
  return Math.abs(matrix[0] - 1) < 1e-9 && Math.abs(matrix[1]) < 1e-9 && Math.abs(matrix[2]) < 1e-9 && Math.abs(matrix[3] - 1) < 1e-9 && Math.abs(matrix[4]) < 1e-9 && Math.abs(matrix[5]) < 1e-9;
}

function svgMatrix(matrix: Matrix): string {
  return `matrix(${matrix.map(formatNumber).join(" ")})`;
}

function dmlBool(value: string | null): boolean {
  return value === "1" || value === "true";
}

function dmlXfrmTransformAttr(spPr: Element, box: Box, options: { skipFlip?: boolean } = {}): string {
  const transform = dmlXfrmTransform(spPr, box, options);
  return transform ? ` transform="${transform}"` : "";
}

function dmlXfrmTransform(spPr: Element, box: Box, options: { skipFlip?: boolean } = {}): string {
  const xfrm = childByLocal(spPr, "xfrm");
  if (!xfrm) return "";
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const transforms: string[] = [];
  const rotation = Number(xfrm.getAttribute("rot"));
  if (Number.isFinite(rotation) && rotation) {
    transforms.push(`rotate(${formatNumber(rotation / 60000)} ${formatNumber(centerX)} ${formatNumber(centerY)})`);
  }
  const flipH = !options.skipFlip && dmlBool(xfrm.getAttribute("flipH"));
  const flipV = !options.skipFlip && dmlBool(xfrm.getAttribute("flipV"));
  if (flipH || flipV) {
    transforms.push(`translate(${formatNumber(centerX)} ${formatNumber(centerY)}) scale(${flipH ? -1 : 1} ${flipV ? -1 : 1}) translate(${formatNumber(-centerX)} ${formatNumber(-centerY)})`);
  }
  return transforms.join(" ");
}

function dmlXfrmTransformBounds(spPr: Element, box: Box, options: { skipFlip?: boolean } = {}): Box {
  const matrix = dmlXfrmTransformMatrix(spPr, box, options);
  return matrixIsIdentity(matrix) ? box : transformedBox(matrix, box.x, box.y, box.width, box.height);
}

function dmlXfrmTransformMatrix(spPr: Element, box: Box, options: { skipFlip?: boolean } = {}): Matrix {
  const xfrm = childByLocal(spPr, "xfrm");
  if (!xfrm) return [1, 0, 0, 1, 0, 0];
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  let matrix: Matrix = [1, 0, 0, 1, 0, 0];
  const rotation = Number(xfrm.getAttribute("rot"));
  if (Number.isFinite(rotation) && rotation) {
    const radians = (rotation / 60000 / 180) * Math.PI;
    matrix = multiply(multiply([1, 0, 0, 1, centerX, centerY], [Math.cos(radians), Math.sin(radians), -Math.sin(radians), Math.cos(radians), 0, 0]), multiply([1, 0, 0, 1, -centerX, -centerY], matrix));
  }
  const flipH = !options.skipFlip && dmlBool(xfrm.getAttribute("flipH"));
  const flipV = !options.skipFlip && dmlBool(xfrm.getAttribute("flipV"));
  if (flipH || flipV) {
    matrix = multiply(multiply([1, 0, 0, 1, centerX, centerY], [flipH ? -1 : 1, 0, 0, flipV ? -1 : 1, 0, 0]), multiply([1, 0, 0, 1, -centerX, -centerY], matrix));
  }
  return matrix;
}

function dmlShapeToSvg(element: Element): DmlSvgItem | null {
  const spPr = childByLocal(element, "spPr");
  if (!spPr) return null;
  const box = dmlXfrmBox(spPr);
  if (!box) return null;
  const preset = childByLocal(spPr, "prstGeom")?.getAttribute("prst") || "rect";
  const name = childByLocal(childByLocal(element, "nvSpPr"), "cNvPr")?.getAttribute("name") || preset;
  const paint = dmlSvgPaint(spPr, element);
  const style = dmlSvgStyle(paint);
  const text = dmlText(element);
  const textAttrs = text ? ` data-text="${xml(text)}"` : "";
  const idAttr = name ? ` id="${xml(dmlSvgId(name))}"` : "";
  const transform = dmlXfrmTransformAttr(spPr, box);
  const bounds = dmlXfrmTransformBounds(spPr, box);
  const body = dmlTextSvg(element, box, {
    fallbackFill: dmlStylePaint(element, "fontRef") ?? { color: paint.fill, alpha: paint.fillAlpha },
    fallbackStroke: dmlTextFallbackStroke(paint),
  });
  const custom = childByLocal(spPr, "custGeom");
  if (custom) {
    const customShape = dmlCustomGeometryToSvg(custom, box, idAttr, textAttrs, style, body, transform, bounds);
    if (customShape) return customShape;
  }
  const presetPoints = dmlPresetPoints(preset, box);
  if (presetPoints.length) {
    const pointsAttr = presetPoints.map(([x, y]) => `${formatNumber(x)},${formatNumber(y)}`).join(" ");
    return {
      bounds,
      svg: `<g${idAttr}${textAttrs}${transform}><polygon points="${pointsAttr}"${style}/>${body}</g>`,
    };
  }
  if (preset === "ellipse" || preset === "oval" || preset === "flowChartConnector") {
    return {
      bounds,
      svg: `<g${idAttr}${textAttrs}${transform}><ellipse cx="${formatNumber(box.x + box.width / 2)}" cy="${formatNumber(box.y + box.height / 2)}" rx="${formatNumber(box.width / 2)}" ry="${formatNumber(box.height / 2)}"${style}/>${body}</g>`,
    };
  }
  if (preset === "line" || preset === "straightConnector1") {
    const [x1, x2] = dmlFlip(spPr, "flipH") ? [box.x + box.width, box.x] : [box.x, box.x + box.width];
    const [y1, y2] = dmlFlip(spPr, "flipV") ? [box.y + box.height, box.y] : [box.y, box.y + box.height];
    return { bounds: dmlXfrmTransformBounds(spPr, box, { skipFlip: true }), svg: `<line${idAttr} x1="${formatNumber(x1)}" y1="${formatNumber(y1)}" x2="${formatNumber(x2)}" y2="${formatNumber(y2)}"${style}${dmlXfrmTransformAttr(spPr, box, { skipFlip: true })}/>` };
  }
  const rx = preset === "roundRect" || preset === "flowChartTerminator" || preset === "flowChartAlternateProcess" ? Math.min(box.width, box.height) / 6 : 0;
  return {
    bounds,
    svg: `<g${idAttr}${textAttrs}${transform}><rect x="${formatNumber(box.x)}" y="${formatNumber(box.y)}" width="${formatNumber(box.width)}" height="${formatNumber(box.height)}"${rx ? ` rx="${formatNumber(rx)}" ry="${formatNumber(rx)}"` : ""}${style}/>${body}</g>`,
  };
}

function dmlPresetPoints(kind: string, box: Box): [number, number][] {
  if (box.width <= 0 || box.height <= 0) return [];
  const left = box.x;
  const centerX = box.x + box.width / 2;
  const right = box.x + box.width;
  const top = box.y;
  const centerY = box.y + box.height / 2;
  const bottom = box.y + box.height;
  const quarterX = box.x + box.width / 4;
  const threeQuarterX = box.x + box.width * 3 / 4;
  const quarterY = box.y + box.height / 4;
  const threeQuarterY = box.y + box.height * 3 / 4;
  const arrowShaftTop = box.y + box.height * 0.4;
  const arrowShaftBottom = box.y + box.height * 0.6;
  const arrowHeadX = box.x + box.width * 0.65;
  const arrowHeadY = box.y + box.height * 0.65;
  if (kind === "triangle" || kind === "flowChartExtract") return [[centerX, top], [right, bottom], [left, bottom]];
  if (kind === "flowChartMerge") return [[left, top], [right, top], [centerX, bottom]];
  if (kind === "rtTriangle") return [[left, top], [right, bottom], [left, bottom]];
  if (kind === "diamond" || kind === "flowChartDecision" || kind === "flowChartSort") return [[centerX, top], [right, centerY], [centerX, bottom], [left, centerY]];
  if (kind === "flowChartCollate") return [[left, top], [right, top], [centerX, centerY], [right, bottom], [left, bottom], [centerX, centerY]];
  if (kind === "parallelogram" || kind === "flowChartData" || kind === "flowChartInputOutput") return [[quarterX, top], [right, top], [threeQuarterX, bottom], [left, bottom]];
  if (kind === "trapezoid" || kind === "flowChartManualInput") return [[quarterX, top], [threeQuarterX, top], [right, bottom], [left, bottom]];
  if (kind === "nonIsoscelesTrapezoid") return [[box.x + box.width * 0.18, top], [right, top], [box.x + box.width * 0.82, bottom], [left, bottom]];
  if (kind === "flowChartManualOperation") return [[left, top], [right, top], [threeQuarterX, bottom], [quarterX, bottom]];
  if (kind === "flowChartDocument") return [[left, top], [right, top], [right, box.y + box.height * 0.82], [threeQuarterX, bottom], [centerX, box.y + box.height * 0.88], [quarterX, bottom], [left, box.y + box.height * 0.82]];
  if (kind === "flowChartPunchedCard") return [[box.x + box.width * 0.18, top], [right, top], [right, bottom], [left, bottom], [left, box.y + box.height * 0.18]];
  if (kind === "flowChartPunchedTape") return [[left, box.y + box.height * 0.12], [quarterX, top], [centerX, box.y + box.height * 0.12], [threeQuarterX, top], [right, box.y + box.height * 0.12], [right, box.y + box.height * 0.88], [threeQuarterX, bottom], [centerX, box.y + box.height * 0.88], [quarterX, bottom], [left, box.y + box.height * 0.88]];
  if (kind === "flowChartDelay") return [[left, top], [box.x + box.width * 0.7, top], [right, centerY], [box.x + box.width * 0.7, bottom], [left, bottom]];
  if (kind === "flowChartStoredData") return [[box.x + box.width * 0.15, top], [right, top], [right, bottom], [box.x + box.width * 0.15, bottom], [left, centerY]];
  if (kind === "flowChartDisplay") return [[left, top], [box.x + box.width * 0.8, top], [right, centerY], [box.x + box.width * 0.8, bottom], [left, bottom], [box.x + box.width * 0.15, centerY]];
  if (kind === "flowChartOffpageConnector") return [[left, top], [right, top], [right, threeQuarterY], [centerX, bottom], [left, threeQuarterY]];
  if (kind === "pentagon") return [[centerX, top], [right, box.y + box.height * 0.38], [box.x + box.width * 0.81, bottom], [box.x + box.width * 0.19, bottom], [left, box.y + box.height * 0.38]];
  if (kind === "hexagon" || kind === "flowChartPreparation") return [[quarterX, top], [threeQuarterX, top], [right, centerY], [threeQuarterX, bottom], [quarterX, bottom], [left, centerY]];
  if (kind === "heptagon") return regularPolygonPoints(7, box);
  if (kind === "octagon") return [[quarterX, top], [threeQuarterX, top], [right, quarterY], [right, threeQuarterY], [threeQuarterX, bottom], [quarterX, bottom], [left, threeQuarterY], [left, quarterY]];
  if (kind === "pie") return [[centerX, centerY], ...ellipseArcPoints(centerX, centerY, box.width / 2, box.height / 2, -90, 0)];
  if (kind === "chord") return ellipseArcPoints(centerX, centerY, box.width / 2, box.height / 2, -90, 90);
  if (kind === "blockArc") return [...ellipseArcPoints(centerX, centerY, box.width / 2, box.height / 2, -90, 0), ...ellipseArcPoints(centerX, centerY, box.width * 0.28, box.height * 0.28, 0, -90)];
  if (kind === "decagon") return regularPolygonPoints(10, box);
  if (kind === "dodecagon" || kind === "flowChartOr" || kind === "flowChartSummingJunction") return regularPolygonPoints(12, box);
  if (kind === "bevel") return [[box.x + box.width * 0.18, top], [right - box.width * 0.18, top], [right, box.y + box.height * 0.18], [right, bottom - box.height * 0.18], [right - box.width * 0.18, bottom], [box.x + box.width * 0.18, bottom], [left, bottom - box.height * 0.18], [left, box.y + box.height * 0.18]];
  if (kind === "snip1Rect") return [[left, top], [threeQuarterX, top], [right, quarterY], [right, bottom], [left, bottom]];
  if (kind === "snip2SameRect") return [[quarterX, top], [right, top], [right, threeQuarterY], [threeQuarterX, bottom], [left, bottom], [left, quarterY]];
  if (kind === "snip2DiagRect") return [[left, top], [threeQuarterX, top], [right, quarterY], [right, bottom], [quarterX, bottom], [left, threeQuarterY]];
  if (kind === "chevron") return [[left, top], [threeQuarterX, top], [right, centerY], [threeQuarterX, bottom], [left, bottom], [quarterX, centerY]];
  if (kind === "homePlate") return [[left, top], [threeQuarterX, top], [right, centerY], [threeQuarterX, bottom], [left, bottom]];
  if (kind === "foldedCorner") return [[left, top], [threeQuarterX, top], [right, quarterY], [right, bottom], [left, bottom]];
  if (kind === "corner" || kind === "halfFrame") return [[left, top], [right, top], [right, quarterY], [quarterX, quarterY], [quarterX, bottom], [left, bottom]];
  if (kind === "diagStripe") return [[left, bottom], [quarterX, bottom], [right, top], [threeQuarterX, top]];
  if (kind === "plaque") return [[box.x + box.width * 0.2, top], [box.x + box.width * 0.8, top], [right, box.y + box.height * 0.2], [right, box.y + box.height * 0.8], [box.x + box.width * 0.8, bottom], [box.x + box.width * 0.2, bottom], [left, box.y + box.height * 0.8], [left, box.y + box.height * 0.2]];
  if (["actionButtonBackPrevious", "actionButtonBeginning", "actionButtonBlank", "actionButtonDocument", "actionButtonEnd", "actionButtonForwardNext", "actionButtonHelp", "actionButtonHome", "actionButtonInformation", "actionButtonMovie", "actionButtonReturn", "actionButtonSound"].includes(kind)) return [[box.x + box.width * 0.12, top], [right - box.width * 0.12, top], [right, box.y + box.height * 0.12], [right, bottom - box.height * 0.12], [right - box.width * 0.12, bottom], [box.x + box.width * 0.12, bottom], [left, bottom - box.height * 0.12], [left, box.y + box.height * 0.12]];
  if (kind === "funnel") return [[left, top], [right, top], [box.x + box.width * 0.62, box.y + box.height * 0.58], [box.x + box.width * 0.62, bottom], [box.x + box.width * 0.38, bottom], [box.x + box.width * 0.38, box.y + box.height * 0.58]];
  if (kind === "wedgeRectCallout") return [[left, top], [right, top], [right, box.y + box.height * 0.68], [box.x + box.width * 0.62, box.y + box.height * 0.68], [box.x + box.width * 0.42, bottom], [box.x + box.width * 0.48, box.y + box.height * 0.68], [left, box.y + box.height * 0.68]];
  if (kind === "wedgeRoundRectCallout") return [[box.x + box.width * 0.12, top], [box.x + box.width * 0.88, top], [right, box.y + box.height * 0.12], [right, box.y + box.height * 0.68], [box.x + box.width * 0.62, box.y + box.height * 0.68], [box.x + box.width * 0.42, bottom], [box.x + box.width * 0.48, box.y + box.height * 0.68], [box.x + box.width * 0.12, box.y + box.height * 0.68], [left, box.y + box.height * 0.56], [left, box.y + box.height * 0.12]];
  if (kind === "wedgeEllipseCallout") return [[centerX, top], [box.x + box.width * 0.85, box.y + box.height * 0.08], [right, box.y + box.height * 0.34], [box.x + box.width * 0.88, box.y + box.height * 0.58], [box.x + box.width * 0.62, box.y + box.height * 0.68], [box.x + box.width * 0.42, bottom], [box.x + box.width * 0.48, box.y + box.height * 0.68], [box.x + box.width * 0.18, box.y + box.height * 0.64], [left, box.y + box.height * 0.38], [box.x + box.width * 0.12, box.y + box.height * 0.12]];
  if (kind === "ribbon") return [[left, box.y + box.height * 0.18], [box.x + box.width * 0.2, box.y + box.height * 0.3], [box.x + box.width * 0.2, top], [box.x + box.width * 0.8, top], [box.x + box.width * 0.8, box.y + box.height * 0.3], [right, box.y + box.height * 0.18], [box.x + box.width * 0.9, centerY], [right, box.y + box.height * 0.82], [box.x + box.width * 0.8, box.y + box.height * 0.7], [box.x + box.width * 0.8, bottom], [box.x + box.width * 0.2, bottom], [box.x + box.width * 0.2, box.y + box.height * 0.7], [left, box.y + box.height * 0.82], [box.x + box.width * 0.1, centerY]];
  if (kind === "ribbon2") return [[left, box.y + box.height * 0.32], [box.x + box.width * 0.2, box.y + box.height * 0.2], [box.x + box.width * 0.2, top], [box.x + box.width * 0.8, top], [box.x + box.width * 0.8, box.y + box.height * 0.2], [right, box.y + box.height * 0.32], [box.x + box.width * 0.9, centerY], [right, box.y + box.height * 0.68], [box.x + box.width * 0.8, box.y + box.height * 0.8], [box.x + box.width * 0.8, bottom], [box.x + box.width * 0.2, bottom], [box.x + box.width * 0.2, box.y + box.height * 0.8], [left, box.y + box.height * 0.68], [box.x + box.width * 0.1, centerY]];
  if (kind === "leftRightRibbon") return [[left, top], [box.x + box.width * 0.18, box.y + box.height * 0.22], [box.x + box.width * 0.18, box.y + box.height * 0.08], [box.x + box.width * 0.82, box.y + box.height * 0.08], [box.x + box.width * 0.82, box.y + box.height * 0.22], [right, top], [box.x + box.width * 0.9, centerY], [right, bottom], [box.x + box.width * 0.82, box.y + box.height * 0.78], [box.x + box.width * 0.82, box.y + box.height * 0.92], [box.x + box.width * 0.18, box.y + box.height * 0.92], [box.x + box.width * 0.18, box.y + box.height * 0.78], [left, bottom], [box.x + box.width * 0.1, centerY]];
  if (kind === "leftBracket") return [[right, top], [left, top], [left, bottom], [right, bottom], [right, threeQuarterY], [quarterX, threeQuarterY], [quarterX, quarterY], [right, quarterY]];
  if (kind === "rightBracket") return [[left, top], [right, top], [right, bottom], [left, bottom], [left, threeQuarterY], [threeQuarterX, threeQuarterY], [threeQuarterX, quarterY], [left, quarterY]];
  if (kind === "leftBrace") return [[right, top], [centerX, top], [quarterX, quarterY], [centerX, centerY], [quarterX, threeQuarterY], [centerX, bottom], [right, bottom], [threeQuarterX, threeQuarterY], [right, centerY], [threeQuarterX, quarterY]];
  if (kind === "rightBrace") return [[left, top], [centerX, top], [threeQuarterX, quarterY], [centerX, centerY], [threeQuarterX, threeQuarterY], [centerX, bottom], [left, bottom], [quarterX, threeQuarterY], [left, centerY], [quarterX, quarterY]];
  if (kind === "plus" || kind === "mathPlus") return [[box.x + box.width * 0.35, top], [box.x + box.width * 0.65, top], [box.x + box.width * 0.65, box.y + box.height * 0.35], [right, box.y + box.height * 0.35], [right, box.y + box.height * 0.65], [box.x + box.width * 0.65, box.y + box.height * 0.65], [box.x + box.width * 0.65, bottom], [box.x + box.width * 0.35, bottom], [box.x + box.width * 0.35, box.y + box.height * 0.65], [left, box.y + box.height * 0.65], [left, box.y + box.height * 0.35], [box.x + box.width * 0.35, box.y + box.height * 0.35]];
  if (kind === "mathMinus") return [[left, arrowShaftTop], [right, arrowShaftTop], [right, arrowShaftBottom], [left, arrowShaftBottom]];
  if (kind === "mathMultiply") return [[box.x + box.width * 0.2, top], [centerX, box.y + box.height * 0.3], [box.x + box.width * 0.8, top], [right, box.y + box.height * 0.2], [box.x + box.width * 0.7, centerY], [right, box.y + box.height * 0.8], [box.x + box.width * 0.8, bottom], [centerX, box.y + box.height * 0.7], [box.x + box.width * 0.2, bottom], [left, box.y + box.height * 0.8], [box.x + box.width * 0.3, centerY], [left, box.y + box.height * 0.2]];
  if (kind === "heart") return [[centerX, bottom], [left, box.y + box.height * 0.45], [box.x + box.width * 0.08, box.y + box.height * 0.18], [box.x + box.width * 0.32, top], [centerX, box.y + box.height * 0.2], [box.x + box.width * 0.68, top], [box.x + box.width * 0.92, box.y + box.height * 0.18], [right, box.y + box.height * 0.45]];
  if (kind === "lightningBolt") return [[box.x + box.width * 0.58, top], [box.x + box.width * 0.18, box.y + box.height * 0.55], [box.x + box.width * 0.46, box.y + box.height * 0.55], [box.x + box.width * 0.36, bottom], [box.x + box.width * 0.82, box.y + box.height * 0.4], [box.x + box.width * 0.54, box.y + box.height * 0.4]];
  if (kind === "teardrop") return [[centerX, top], [box.x + box.width * 0.82, box.y + box.height * 0.08], [right, box.y + box.height * 0.38], [box.x + box.width * 0.88, box.y + box.height * 0.72], [centerX, bottom], [box.x + box.width * 0.18, box.y + box.height * 0.72], [left, box.y + box.height * 0.38], [box.x + box.width * 0.18, box.y + box.height * 0.12]];
  if (kind === "moon") return [...ellipseArcPoints(centerX, centerY, box.width / 2, box.height / 2, -90, 270, 16), ...ellipseArcPoints(box.x + box.width * 0.62, centerY, box.width * 0.34, box.height * 0.42, 270, -90, 16)];
  if (kind === "cloud") return [[box.x + box.width * 0.15, box.y + box.height * 0.62], [box.x + box.width * 0.08, box.y + box.height * 0.48], [box.x + box.width * 0.2, box.y + box.height * 0.36], [box.x + box.width * 0.34, box.y + box.height * 0.38], [box.x + box.width * 0.42, box.y + box.height * 0.22], [box.x + box.width * 0.62, box.y + box.height * 0.2], [box.x + box.width * 0.72, box.y + box.height * 0.35], [box.x + box.width * 0.86, box.y + box.height * 0.36], [box.x + box.width * 0.96, box.y + box.height * 0.52], [box.x + box.width * 0.88, box.y + box.height * 0.7], [box.x + box.width * 0.62, box.y + box.height * 0.76], [box.x + box.width * 0.38, box.y + box.height * 0.74], [box.x + box.width * 0.22, box.y + box.height * 0.74]];
  if (kind === "star4") return [[centerX, top], [box.x + box.width * 0.6, box.y + box.height * 0.4], [right, centerY], [box.x + box.width * 0.6, box.y + box.height * 0.6], [centerX, bottom], [box.x + box.width * 0.4, box.y + box.height * 0.6], [left, centerY], [box.x + box.width * 0.4, box.y + box.height * 0.4]];
  if (kind === "star5") return [[centerX, top], [box.x + box.width * 0.62, box.y + box.height * 0.38], [right, box.y + box.height * 0.38], [box.x + box.width * 0.69, box.y + box.height * 0.59], [box.x + box.width * 0.81, bottom], [centerX, box.y + box.height * 0.72], [box.x + box.width * 0.19, bottom], [box.x + box.width * 0.31, box.y + box.height * 0.59], [left, box.y + box.height * 0.38], [box.x + box.width * 0.38, box.y + box.height * 0.38]];
  if (kind === "star6") return [[centerX, top], [box.x + box.width * 0.6, box.y + box.height * 0.33], [box.x + box.width * 0.93, quarterY], [box.x + box.width * 0.7, centerY], [box.x + box.width * 0.93, threeQuarterY], [box.x + box.width * 0.6, box.y + box.height * 0.67], [centerX, bottom], [box.x + box.width * 0.4, box.y + box.height * 0.67], [box.x + box.width * 0.07, threeQuarterY], [box.x + box.width * 0.3, centerY], [box.x + box.width * 0.07, quarterY], [box.x + box.width * 0.4, box.y + box.height * 0.33]];
  if (kind === "star8") return [[centerX, top], [box.x + box.width * 0.58, box.y + box.height * 0.32], [box.x + box.width * 0.85, box.y + box.height * 0.15], [box.x + box.width * 0.68, box.y + box.height * 0.42], [right, centerY], [box.x + box.width * 0.68, box.y + box.height * 0.58], [box.x + box.width * 0.85, box.y + box.height * 0.85], [box.x + box.width * 0.58, box.y + box.height * 0.68], [centerX, bottom], [box.x + box.width * 0.42, box.y + box.height * 0.68], [box.x + box.width * 0.15, box.y + box.height * 0.85], [box.x + box.width * 0.32, box.y + box.height * 0.58], [left, centerY], [box.x + box.width * 0.32, box.y + box.height * 0.42], [box.x + box.width * 0.15, box.y + box.height * 0.15], [box.x + box.width * 0.42, box.y + box.height * 0.32]];
  if (kind === "star10") return [[centerX, top], [box.x + box.width * 0.56, box.y + box.height * 0.36], [box.x + box.width * 0.79, box.y + box.height * 0.1], [box.x + box.width * 0.68, box.y + box.height * 0.43], [right, box.y + box.height * 0.35], [box.x + box.width * 0.7, box.y + box.height * 0.55], [box.x + box.width * 0.98, box.y + box.height * 0.65], [box.x + box.width * 0.64, box.y + box.height * 0.63], [box.x + box.width * 0.65, box.y + box.height * 0.95], [centerX, box.y + box.height * 0.7], [box.x + box.width * 0.35, box.y + box.height * 0.95], [box.x + box.width * 0.36, box.y + box.height * 0.63], [box.x + box.width * 0.02, box.y + box.height * 0.65], [box.x + box.width * 0.3, box.y + box.height * 0.55], [left, box.y + box.height * 0.35], [box.x + box.width * 0.32, box.y + box.height * 0.43], [box.x + box.width * 0.21, box.y + box.height * 0.1], [box.x + box.width * 0.44, box.y + box.height * 0.36]];
  if (kind === "star12") return regularStarPoints(12, box);
  if (kind === "star16") return regularStarPoints(16, box);
  if (kind === "sun") return regularStarPoints(16, box, 0.72);
  if (kind === "irregularSeal1") return regularStarPoints(16, box, 0.62);
  if (kind === "irregularSeal2") return regularStarPoints(24, box, 0.68);
  if (kind === "rightArrow") return [[left, quarterY], [arrowHeadX, quarterY], [arrowHeadX, top], [right, centerY], [arrowHeadX, bottom], [arrowHeadX, threeQuarterY], [left, threeQuarterY]];
  if (kind === "notchedRightArrow") return [[left, quarterY], [arrowHeadX, quarterY], [arrowHeadX, top], [right, centerY], [arrowHeadX, bottom], [arrowHeadX, threeQuarterY], [left, threeQuarterY], [quarterX, centerY]];
  if (kind === "leftArrow") return [[right, quarterY], [box.x + box.width * 0.35, quarterY], [box.x + box.width * 0.35, top], [left, centerY], [box.x + box.width * 0.35, bottom], [box.x + box.width * 0.35, threeQuarterY], [right, threeQuarterY]];
  if (kind === "upArrow") return [[quarterX, bottom], [quarterX, box.y + box.height * 0.35], [left, box.y + box.height * 0.35], [centerX, top], [right, box.y + box.height * 0.35], [threeQuarterX, box.y + box.height * 0.35], [threeQuarterX, bottom]];
  if (kind === "downArrow") return [[quarterX, top], [quarterX, arrowHeadY], [left, arrowHeadY], [centerX, bottom], [right, arrowHeadY], [threeQuarterX, arrowHeadY], [threeQuarterX, top]];
  if (kind === "leftRightArrow") return [[left, centerY], [quarterX, top], [quarterX, quarterY], [threeQuarterX, quarterY], [threeQuarterX, top], [right, centerY], [threeQuarterX, bottom], [threeQuarterX, threeQuarterY], [quarterX, threeQuarterY], [quarterX, bottom]];
  if (kind === "upDownArrow") return [[centerX, top], [right, quarterY], [threeQuarterX, quarterY], [threeQuarterX, threeQuarterY], [right, threeQuarterY], [centerX, bottom], [left, threeQuarterY], [quarterX, threeQuarterY], [quarterX, quarterY], [left, quarterY]];
  if (kind === "quadArrow") return [[centerX, top], [threeQuarterX, quarterY], [box.x + box.width * 0.6, quarterY], [box.x + box.width * 0.6, arrowShaftTop], [threeQuarterX, arrowShaftTop], [right, centerY], [threeQuarterX, arrowShaftBottom], [box.x + box.width * 0.6, arrowShaftBottom], [box.x + box.width * 0.6, threeQuarterY], [threeQuarterX, threeQuarterY], [centerX, bottom], [quarterX, threeQuarterY], [box.x + box.width * 0.4, threeQuarterY], [box.x + box.width * 0.4, arrowShaftBottom], [quarterX, arrowShaftBottom], [left, centerY], [quarterX, arrowShaftTop], [box.x + box.width * 0.4, arrowShaftTop], [box.x + box.width * 0.4, quarterY], [quarterX, quarterY]];
  if (kind === "leftRightUpArrow") return [[centerX, top], [right, quarterY], [threeQuarterX, quarterY], [threeQuarterX, arrowShaftTop], [right, arrowShaftTop], [right, arrowShaftBottom], [threeQuarterX, arrowShaftBottom], [threeQuarterX, bottom], [quarterX, bottom], [quarterX, arrowShaftBottom], [left, arrowShaftBottom], [left, arrowShaftTop], [quarterX, arrowShaftTop], [quarterX, quarterY], [left, quarterY]];
  if (kind === "bentUpArrow") return [[box.x + box.width * 0.55, bottom], [box.x + box.width * 0.55, quarterY], [box.x + box.width * 0.35, quarterY], [box.x + box.width * 0.7, top], [right, quarterY], [box.x + box.width * 0.8, quarterY], [box.x + box.width * 0.8, bottom]];
  if (kind === "bentArrow") return [[left, top], [box.x + box.width * 0.55, top], [box.x + box.width * 0.55, arrowShaftTop], [arrowHeadX, arrowShaftTop], [arrowHeadX, quarterY], [right, centerY], [arrowHeadX, threeQuarterY], [arrowHeadX, arrowShaftBottom], [box.x + box.width * 0.35, arrowShaftBottom], [box.x + box.width * 0.35, bottom], [left, bottom]];
  if (kind === "uturnArrow") return [[centerX, top], [right, quarterY], [box.x + box.width * 0.7, quarterY], [box.x + box.width * 0.7, bottom], [box.x + box.width * 0.45, bottom], [box.x + box.width * 0.45, quarterY], [quarterX, quarterY], [quarterX, box.y + box.height * 0.08], [left, centerY], [quarterX, box.y + box.height * 0.92], [quarterX, threeQuarterY], [centerX, threeQuarterY]];
  if (kind === "leftUpArrow") return [[centerX, top], [threeQuarterX, quarterY], [box.x + box.width * 0.6, quarterY], [box.x + box.width * 0.6, bottom], [box.x + box.width * 0.4, bottom], [box.x + box.width * 0.4, arrowShaftBottom], [quarterX, arrowShaftBottom], [quarterX, threeQuarterY], [left, centerY], [quarterX, quarterY], [quarterX, arrowShaftTop], [box.x + box.width * 0.4, arrowShaftTop], [box.x + box.width * 0.4, quarterY], [quarterX, quarterY]];
  return [];
}

function regularPolygonPoints(sides: number, box: Box): [number, number][] {
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const radiusX = box.width / 2;
  const radiusY = box.height / 2;
  return Array.from({ length: sides }, (_, index) => {
    const angle = -Math.PI / 2 + (2 * Math.PI * index) / sides;
    return [centerX + radiusX * Math.cos(angle), centerY + radiusY * Math.sin(angle)] as [number, number];
  });
}

function regularStarPoints(points: number, box: Box, innerScale = 0.55): [number, number][] {
  const centerX = box.x + box.width / 2;
  const centerY = box.y + box.height / 2;
  const outerX = box.width / 2;
  const outerY = box.height / 2;
  const innerX = outerX * innerScale;
  const innerY = outerY * innerScale;
  return Array.from({ length: points * 2 }, (_, index) => {
    const radiusX = index % 2 === 0 ? outerX : innerX;
    const radiusY = index % 2 === 0 ? outerY : innerY;
    const angle = -Math.PI / 2 + (Math.PI * index) / points;
    return [centerX + radiusX * Math.cos(angle), centerY + radiusY * Math.sin(angle)] as [number, number];
  });
}

function ellipseArcPoints(centerX: number, centerY: number, radiusX: number, radiusY: number, startDegrees: number, endDegrees: number, segments = 12): [number, number][] {
  return Array.from({ length: segments + 1 }, (_, index) => {
    const degrees = startDegrees + ((endDegrees - startDegrees) * index) / segments;
    const radians = (degrees / 180) * Math.PI;
    return [centerX + Math.cos(radians) * radiusX, centerY + Math.sin(radians) * radiusY] as [number, number];
  });
}

function dmlCustomGeometryToSvg(custom: Element, box: Box, idAttr: string, textAttrs: string, style: string, body: string, transform = "", transformedBounds: Box | null = null): DmlSvgItem | null {
  const points = dmlCustomPoints(custom, box.x, box.y);
  if (points.points.length < 2) return null;
  const tag = points.closed ? "polygon" : "polyline";
  const pointsAttr = points.points.map(([x, y]) => `${formatNumber(x)},${formatNumber(y)}`).join(" ");
  const bounds = pointsBox(points.points);
  return {
    bounds: transformedBounds ?? bounds,
    svg: `<g${idAttr}${textAttrs}${transform}><${tag} points="${pointsAttr}"${style}/>${body}</g>`,
  };
}

function dmlCustomPoints(custom: Element, x: number, y: number): { points: [number, number][]; closed: boolean } {
  const result: [number, number][] = [];
  let closed = false;
  const pathList = childByLocal(custom, "pathLst");
  if (!pathList) return { points: result, closed };
  for (const command of dmlCustomCommands(pathList)) {
    const tag = localName(command);
    if (tag === "moveTo" || tag === "lnTo") {
      const pointValue = dmlPathPoint(childByLocal(command, "pt"), x, y);
      if (pointValue) result.push(pointValue);
    } else if (tag === "quadBezTo" && result.length) {
      const bezierPoints = directChildrenByLocal(command, "pt").map((pt) => dmlPathPoint(pt, x, y)).filter((pt): pt is [number, number] => pt !== null);
      if (bezierPoints.length >= 2) result.push(...quadraticPoints(result[result.length - 1]!, bezierPoints[0]!, bezierPoints[1]!));
    } else if (tag === "cubicBezTo" && result.length) {
      const bezierPoints = directChildrenByLocal(command, "pt").map((pt) => dmlPathPoint(pt, x, y)).filter((pt): pt is [number, number] => pt !== null);
      if (bezierPoints.length >= 3) result.push(...cubicPoints(result[result.length - 1]!, bezierPoints[0]!, bezierPoints[1]!, bezierPoints[2]!));
    } else if (tag === "close") {
      closed = true;
    }
  }
  return { points: result, closed };
}

function dmlCustomCommands(element: Element): Element[] {
  const commands: Element[] = [];
  const visit = (current: Element): void => {
    for (const child of Array.from(current.children)) {
      if (["moveTo", "lnTo", "quadBezTo", "cubicBezTo", "close"].includes(localName(child))) {
        commands.push(child);
      } else {
        visit(child);
      }
    }
  };
  visit(element);
  return commands;
}

function dmlPathPoint(pt: Element | null, x: number, y: number): [number, number] | null {
  if (!pt) return null;
  const pointX = Number(pt.getAttribute("x"));
  const pointY = Number(pt.getAttribute("y"));
  if (!Number.isFinite(pointX) || !Number.isFinite(pointY)) return null;
  return [x + pointX / emuPerPx, y + pointY / emuPerPx];
}

function pointsBox(points: [number, number][]): Box {
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, width: Math.max(...xs) - x, height: Math.max(...ys) - y };
}

function dmlConnectorToSvg(element: Element): DmlSvgItem | null {
  const spPr = childByLocal(element, "spPr");
  if (!spPr) return null;
  const box = dmlXfrmBox(spPr);
  if (!box) return null;
  const name = childByLocal(childByLocal(element, "nvCxnSpPr"), "cNvPr")?.getAttribute("name") || "connector";
  const [x1, x2] = dmlFlip(spPr, "flipH") ? [box.x + box.width, box.x] : [box.x, box.x + box.width];
  const [y1, y2] = dmlFlip(spPr, "flipV") ? [box.y + box.height, box.y] : [box.y, box.y + box.height];
  return {
    bounds: dmlXfrmTransformBounds(spPr, box, { skipFlip: true }),
    svg: `<line id="${xml(dmlSvgId(name))}" x1="${formatNumber(x1)}" y1="${formatNumber(y1)}" x2="${formatNumber(x2)}" y2="${formatNumber(y2)}"${dmlSvgStyle(dmlSvgPaint(spPr, element))} data-kind="relation"${dmlXfrmTransformAttr(spPr, box, { skipFlip: true })}/>`,
  };
}

function dmlPictureToSvg(element: Element): DmlSvgItem | null {
  const spPr = childByLocal(element, "spPr");
  const blip = descendantsByLocal(element, "blip")[0];
  if (!spPr || !blip) return null;
  const box = dmlXfrmBox(spPr);
  if (!box) return null;
  const href = attrByLocal(blip, "embed");
  if (!href) return null;
  const name = childByLocal(childByLocal(element, "nvPicPr"), "cNvPr")?.getAttribute("name") || "image";
  const opacity = dmlBlipAlpha(blip);
  const preserve = dmlPicturePreserveAspectRatio(element);
  const transform = dmlXfrmTransformAttr(spPr, box);
  const attrs = [
    `id="${xml(dmlSvgId(name))}"`,
    `href="${xml(href)}"`,
    `x="${formatNumber(box.x)}"`,
    `y="${formatNumber(box.y)}"`,
    `width="${formatNumber(box.width)}"`,
    `height="${formatNumber(box.height)}"`,
    opacity == null || opacity >= 1 ? "" : `opacity="${formatNumber(opacity)}"`,
    preserve ? `preserveAspectRatio="${preserve}"` : "",
    transform ? transform.trim() : "",
  ].filter(Boolean);
  return {
    bounds: dmlXfrmTransformBounds(spPr, box),
    svg: `<image ${attrs.join(" ")}/>`,
  };
}

function dmlPicturePreserveAspectRatio(element: Element): string | null {
  const rect = descendantsByLocal(element, "srcRect")[0];
  if (!rect) return null;
  const left = dmlInt(rect.getAttribute("l"), 0);
  const top = dmlInt(rect.getAttribute("t"), 0);
  const right = dmlInt(rect.getAttribute("r"), 0);
  const bottom = dmlInt(rect.getAttribute("b"), 0);
  if (!left && !top && !right && !bottom) return null;
  const x = dmlCropAlignment(left, right, "x");
  const y = dmlCropAlignment(top, bottom, "y");
  return `${x}${y} slice`;
}

function dmlCropAlignment(before: number, after: number, axis: "x" | "y"): string {
  if (!before && !after) return axis === "x" ? "xMid" : "YMid";
  if (!before) return axis === "x" ? "xMin" : "YMin";
  if (!after) return axis === "x" ? "xMax" : "YMax";
  return axis === "x" ? "xMid" : "YMid";
}

function dmlBlipAlpha(blip: Element): number | null {
  const alphaModFix = childByLocal(blip, "alphaModFix");
  if (alphaModFix?.getAttribute("amt") != null) {
    const value = dmlInt(alphaModFix.getAttribute("amt"), Number.NaN);
    return Number.isFinite(value) ? value / 100000 : null;
  }
  let result: number | null = null;
  const alpha = descendantsByLocal(blip, "alpha")[0];
  if (alpha?.getAttribute("val") != null) {
    const value = dmlInt(alpha.getAttribute("val"), Number.NaN);
    if (Number.isFinite(value)) result = value / 100000;
  }
  const alphaMod = descendantsByLocal(blip, "alphaMod")[0];
  if (alphaMod?.getAttribute("amt") != null) {
    const value = dmlInt(alphaMod.getAttribute("amt"), Number.NaN);
    if (Number.isFinite(value)) result = (result ?? 1) * (value / 100000);
  }
  return result;
}

function dmlTableFrameToSvg(element: Element): DmlSvgItem | null {
  const tbl = descendantsByLocal(element, "tbl")[0];
  if (!tbl) return null;
  const xfrm = childByLocal(element, "xfrm");
  const off = childByLocal(xfrm, "off");
  const ext = childByLocal(xfrm, "ext");
  const originX = emuToPx(off?.getAttribute("x"));
  const originY = emuToPx(off?.getAttribute("y"));
  const rawColumns = dmlTableColumns(tbl);
  const rawRows = directChildrenByLocal(tbl, "tr").map((row) => emuToPx(row.getAttribute("h")));
  if (!rawColumns.length || !rawRows.length) return null;
  const name = childByLocal(childByLocal(element, "nvGraphicFramePr"), "cNvPr")?.getAttribute("name") || "table";
  const rawWidth = rawColumns.reduce((total, value) => total + value, 0);
  const rawHeight = rawRows.reduce((total, value) => total + value, 0);
  const frameWidth = emuToPx(ext?.getAttribute("cx"));
  const frameHeight = emuToPx(ext?.getAttribute("cy"));
  const scaleX = frameWidth > 0 && rawWidth > 0 ? frameWidth / rawWidth : 1;
  const scaleY = frameHeight > 0 && rawHeight > 0 ? frameHeight / rawHeight : 1;
  const columns = rawColumns.map((value) => value * scaleX);
  const rows = rawRows.map((value) => value * scaleY);
  const width = columns.reduce((total, value) => total + value, 0);
  const height = rows.reduce((total, value) => total + value, 0);
  const occupied: boolean[][] = rows.map(() => columns.map(() => false));
  const children: string[] = [];
  let rowY = originY;
  directChildrenByLocal(tbl, "tr").forEach((row, rowIndex) => {
    let colX = originX;
    let colIndex = 0;
    for (const cell of directChildrenByLocal(row, "tc")) {
      const colSpan = Math.max(1, Number(cell.getAttribute("gridSpan") || 1) || 1);
      const rowSpan = Math.max(1, Number(cell.getAttribute("rowSpan") || 1) || 1);
      const hMerge = dmlTruthyAttr(cell, "hMerge");
      const vMerge = dmlTruthyAttr(cell, "vMerge");
      if (vMerge && !hMerge && occupied[rowIndex]?.[colIndex]) {
        colX += columns.slice(colIndex, colIndex + colSpan).reduce((total, value) => total + value, 0);
        colIndex += colSpan;
        continue;
      }
      while (occupied[rowIndex]?.[colIndex]) {
        colX += columns[colIndex] ?? 0;
        colIndex += 1;
      }
      const isMerge = hMerge || vMerge;
      const cellWidth = columns.slice(colIndex, colIndex + colSpan).reduce((total, value) => total + value, 0);
      const cellHeight = rows.slice(rowIndex, rowIndex + rowSpan).reduce((total, value) => total + value, 0);
      for (let r = rowIndex; r < Math.min(rows.length, rowIndex + rowSpan); r += 1) {
        for (let c = colIndex; c < Math.min(columns.length, colIndex + colSpan); c += 1) occupied[r]![c] = true;
      }
      if (!isMerge && cellWidth > 0 && cellHeight > 0) {
        const text = dmlText(cell);
        const fillPaint = dmlFillPaint(childByLocal(cell, "tcPr") ?? cell);
        const cellAttrs = [
          `data-kind="cell"`,
          `data-row="${rowIndex}"`,
          `data-col="${colIndex}"`,
          colSpan > 1 ? `data-colspan="${colSpan}"` : "",
          rowSpan > 1 ? `data-rowspan="${rowSpan}"` : "",
          text ? `data-text="${xml(text)}"` : "",
        ].filter(Boolean).join(" ");
        children.push(`<rect ${cellAttrs} x="${formatNumber(colX)}" y="${formatNumber(rowY)}" width="${formatNumber(cellWidth)}" height="${formatNumber(cellHeight)}"${dmlSvgStyle({ fill: fillPaint?.color ?? null, fillAlpha: fillPaint?.alpha ?? null, stroke: null, strokeWidth: null })}/>`);
        children.push(...dmlTableCellBorderLines(childByLocal(cell, "tcPr"), colX, rowY, cellWidth, cellHeight));
        if (text) {
          children.push(dmlTextSvg(cell, { x: colX, y: rowY, width: cellWidth, height: cellHeight }, { defaultBaseline: "middle", defaultFill: "#000000", defaultStroke: "none", insetScaleX: scaleX, insetScaleY: scaleY }));
        }
      }
      colX += cellWidth;
      colIndex += colSpan;
    }
    rowY += rows[rowIndex] ?? 0;
  });
  return {
    bounds: { x: originX, y: originY, width, height },
    svg: `<g id="${xml(dmlSvgId(name))}" data-kind="table">${children.join("")}</g>`,
  };
}

function dmlTableColumns(tbl: Element): number[] {
  const grid = childByLocal(tbl, "tblGrid");
  return grid ? directChildrenByLocal(grid, "gridCol").map((col) => emuToPx(col.getAttribute("w"))) : [];
}

function dmlTruthyAttr(element: Element, name: string): boolean {
  const value = element.getAttribute(name);
  return value != null && !["", "0", "false", "none"].includes(value.trim().toLowerCase());
}

function dmlTableCellBorderLines(tcPr: Element | null, x: number, y: number, width: number, height: number): string[] {
  const specs: Array<[string, number, number, number, number]> = [
    ["lnL", x, y, x, y + height],
    ["lnR", x + width, y, x + width, y + height],
    ["lnT", x, y, x + width, y],
    ["lnB", x, y + height, x + width, y + height],
  ];
  return specs.flatMap(([name, x1, y1, x2, y2]) => {
    const style = dmlTableCellBorderStyle(tcPr, name);
    if (!style) return [];
    return [`<line x1="${formatNumber(x1)}" y1="${formatNumber(y1)}" x2="${formatNumber(x2)}" y2="${formatNumber(y2)}"${style}/>`];
  });
}

function dmlTableCellBorderStyle(tcPr: Element | null, name: string): string | null {
  const line = childByLocal(tcPr, name);
  if (line && childByLocal(line, "noFill")) return null;
  const strokeWidth = line ? emuToPx(line.getAttribute("w")) || 1 : 1;
  const paint = line ? dmlFillPaint(line) : null;
  return dmlSvgStyle({
    fill: null,
    stroke: paint?.color ?? "#000000",
    strokeAlpha: paint?.alpha ?? null,
    strokeWidth,
    strokeLineCap: dmlLineCap(line?.getAttribute("cap") ?? null),
    strokeLineJoin: line ? dmlLineJoin(line) : null,
    strokeDasharray: line ? dmlDasharray(line, strokeWidth) : null,
    strokeMiterlimit: line ? dmlMiterlimit(line) : null,
  });
}

function attrByLocal(element: Element, name: string): string | null {
  for (let index = 0; index < element.attributes.length; index += 1) {
    const attr = element.attributes.item(index);
    if (attr && (attr.localName || attr.name.replace(/^.*:/, "")) === name) return attr.value;
  }
  return null;
}

function optionalInt(value: string | null): number {
  const parsed = Number.parseInt(value ?? "", 10);
  return Number.isFinite(parsed) ? parsed : 0;
}

function dmlXfrmBox(spPr: Element): Box | null {
  const xfrm = childByLocal(spPr, "xfrm");
  const off = childByLocal(xfrm, "off");
  const ext = childByLocal(xfrm, "ext");
  if (!off || !ext) return null;
  return {
    x: emuToPx(off.getAttribute("x")),
    y: emuToPx(off.getAttribute("y")),
    width: Math.max(0, emuToPx(ext.getAttribute("cx"))),
    height: Math.max(0, emuToPx(ext.getAttribute("cy"))),
  };
}

type DmlPaint = { color: string | null; alpha: number | null };
type DmlStrokePaint = { color: string | null; alpha: number | null; width: number | null; lineCap: string | null; lineJoin: string | null; dasharray: string | null; miterlimit: number | null };

function dmlSvgPaint(spPr: Element, element: Element | null = null): { fill: string | null; fillAlpha: number | null; stroke: string | null; strokeAlpha: number | null; strokeWidth: number | null; strokeLineCap: string | null; strokeLineJoin: string | null; strokeDasharray: string | null; strokeMiterlimit: number | null; markerStart: string | null; markerEnd: string | null } {
  const fillPaint = childByLocal(spPr, "noFill") ? { color: null, alpha: null } : dmlFillPaint(spPr) ?? dmlStylePaint(element, "fillRef") ?? { color: "#000000", alpha: null };
  const ln = childByLocal(spPr, "ln");
  const styleStroke = dmlStylePaint(element, "lnRef");
  const strokePaint = ln ? (childByLocal(ln, "noFill") ? null : dmlFillPaint(ln) ?? styleStroke) : styleStroke;
  const strokeWidth = ln ? emuToPx(ln.getAttribute("w")) : null;
  return {
    fill: fillPaint.color,
    fillAlpha: fillPaint.alpha,
    stroke: strokePaint?.color ?? null,
    strokeAlpha: strokePaint?.alpha ?? null,
    strokeWidth,
    strokeLineCap: dmlLineCap(ln?.getAttribute("cap") ?? null),
    strokeLineJoin: ln ? dmlLineJoin(ln) : null,
    strokeDasharray: ln ? dmlDasharray(ln, strokeWidth) : null,
    strokeMiterlimit: ln ? dmlMiterlimit(ln) : null,
    markerStart: ln ? dmlLineArrow(childByLocal(ln, "tailEnd")) : null,
    markerEnd: ln ? dmlLineArrow(childByLocal(ln, "headEnd")) : null,
  };
}

function dmlSvgStyle(paint: { fill: string | null; fillAlpha?: number | null; stroke: string | null; strokeAlpha?: number | null; strokeWidth: number | null; strokeLineCap?: string | null; strokeLineJoin?: string | null; strokeDasharray?: string | null; strokeMiterlimit?: number | null; markerStart?: string | null; markerEnd?: string | null }): string {
  const attrs = [
    `fill="${paint.fill ?? "none"}"`,
    paint.fillAlpha != null && paint.fillAlpha < 1 ? `fill-opacity="${formatNumber(paint.fillAlpha)}"` : "",
    paint.stroke ? `stroke="${paint.stroke}"` : "",
    paint.stroke && paint.strokeAlpha != null && paint.strokeAlpha < 1 ? `stroke-opacity="${formatNumber(paint.strokeAlpha)}"` : "",
    paint.stroke && paint.strokeWidth != null ? `stroke-width="${formatNumber(paint.strokeWidth)}"` : "",
    paint.stroke && paint.strokeLineCap ? `stroke-linecap="${paint.strokeLineCap}"` : "",
    paint.stroke && paint.strokeLineJoin ? `stroke-linejoin="${paint.strokeLineJoin}"` : "",
    paint.stroke && paint.strokeDasharray ? `stroke-dasharray="${paint.strokeDasharray}"` : "",
    paint.stroke && paint.strokeMiterlimit != null ? `stroke-miterlimit="${formatNumber(paint.strokeMiterlimit)}"` : "",
    paint.markerStart ? `marker-start="url(#${xml(paint.markerStart)})"` : "",
    paint.markerEnd ? `marker-end="url(#${xml(paint.markerEnd)})"` : "",
  ].filter(Boolean);
  return attrs.length ? ` ${attrs.join(" ")}` : "";
}

function dmlTextFallbackStroke(paint: { stroke: string | null; strokeAlpha?: number | null; strokeWidth: number | null; strokeLineCap?: string | null; strokeLineJoin?: string | null; strokeDasharray?: string | null; strokeMiterlimit?: number | null }): DmlStrokePaint | null {
  if (!paint.stroke) return null;
  return {
    color: paint.stroke,
    alpha: paint.strokeAlpha ?? null,
    width: paint.strokeWidth,
    lineCap: paint.strokeLineCap ?? null,
    lineJoin: paint.strokeLineJoin ?? null,
    dasharray: paint.strokeDasharray ?? null,
    miterlimit: paint.strokeMiterlimit ?? null,
  };
}

function dmlStylePaint(element: Element | null | undefined, name: string): DmlPaint | null {
  const ref = childByLocal(childByLocal(element, "style"), name);
  return ref ? { color: dmlColor(ref), alpha: dmlAlpha(ref) } : null;
}

function dmlFillPaint(parent: Element): DmlPaint | null {
  const solidFill = childByLocal(parent, "solidFill");
  if (solidFill) return { color: dmlColor(solidFill), alpha: dmlAlpha(solidFill) };
  const gradFill = childByLocal(parent, "gradFill");
  if (gradFill) return dmlAveragePaint(directChildrenByLocal(childByLocal(gradFill, "gsLst"), "gs"));
  const patternFill = childByLocal(parent, "pattFill");
  if (patternFill) return dmlAveragePaint(["fgClr", "bgClr"].map((name) => childByLocal(patternFill, name)).filter((item): item is Element => Boolean(item)));
  return null;
}

function dmlAveragePaint(elements: Element[]): DmlPaint | null {
  const colors = elements.map((element) => {
    const color = dmlColor(element);
    const rgb = hexToRgb(color || "");
    if (!rgb) return null;
    return { rgb, alpha: dmlAlpha(element) ?? 1 };
  }).filter((item): item is { rgb: [number, number, number]; alpha: number } => Boolean(item));
  if (!colors.length) return null;
  const count = colors.length;
  return {
    color: rgbToHex([
      dmlRound(colors.reduce((total, item) => total + item.rgb[0], 0) / count),
      dmlRound(colors.reduce((total, item) => total + item.rgb[1], 0) / count),
      dmlRound(colors.reduce((total, item) => total + item.rgb[2], 0) / count),
    ]),
    alpha: dmlAverageAlpha(colors.map((item) => item.alpha)),
  };
}

function dmlAverageAlpha(values: number[]): number | null {
  if (!values.length) return null;
  const alpha = values.reduce((total, value) => total + value, 0) / values.length;
  return alpha < 1 ? alpha : null;
}

function dmlLineCap(value: string | null): string | null {
  return ({ flat: "butt", rnd: "round", sq: "square" } as Record<string, string>)[value || ""] ?? null;
}

function dmlLineArrow(element: Element | null): string | null {
  const type = element?.getAttribute("type");
  return type && type !== "none" ? "svgraph-arrow" : null;
}

function dmlLineJoin(ln: Element): string | null {
  if (childByLocal(ln, "round")) return "round";
  if (childByLocal(ln, "bevel")) return "bevel";
  if (childByLocal(ln, "miter")) return "miter";
  return null;
}

function dmlMiterlimit(ln: Element): number | null {
  const miter = childByLocal(ln, "miter");
  if (!miter?.getAttribute("lim")) return null;
  const value = dmlInt(miter.getAttribute("lim"), Number.NaN);
  return Number.isFinite(value) ? value / 100000 : null;
}

function dmlDasharray(ln: Element, strokeWidth: number | null): string | null {
  const custom = childByLocal(ln, "custDash");
  if (custom && strokeWidth) {
    const values = directChildrenByLocal(custom, "ds").flatMap((item) => [
      formatNumber((dmlInt(item.getAttribute("d"), 0) / 100000) * strokeWidth),
      formatNumber((dmlInt(item.getAttribute("sp"), 0) / 100000) * strokeWidth),
    ]);
    return values.length ? values.join(" ") : null;
  }
  const dash = childByLocal(ln, "prstDash")?.getAttribute("val") || "";
  return ({
    dash: "4 3",
    dashDot: "4 3 1 3",
    dot: "1 3",
    lgDash: "8 3",
    lgDashDot: "8 3 1 3",
    lgDashDotDot: "8 3 1 3 1 3",
    sysDash: "3 1",
    sysDashDot: "3 1 1 1",
    sysDashDotDot: "3 1 1 1 1 1",
    sysDot: "1 1",
  } as Record<string, string>)[dash] ?? null;
}

function dmlColor(parent: Element | null | undefined): string | null {
  if (!parent) return null;
  const srgb = childByLocal(parent, "srgbClr");
  if (srgb?.getAttribute("val")) return dmlApplyLuminanceModifiers(dmlHexColor(srgb.getAttribute("val")), srgb);
  const scrgb = childByLocal(parent, "scrgbClr");
  if (scrgb) return dmlScrgbColor(scrgb);
  const hsl = childByLocal(parent, "hslClr");
  if (hsl) return dmlHslColor(hsl);
  const scheme = childByLocal(parent, "schemeClr");
  if (scheme?.getAttribute("val")) return dmlSchemeColor(scheme);
  const system = childByLocal(parent, "sysClr");
  if (system?.getAttribute("lastClr")) return dmlApplyLuminanceModifiers(dmlHexColor(system.getAttribute("lastClr")), system);
  const preset = childByLocal(parent, "prstClr");
  if (preset?.getAttribute("val")) return dmlPresetColor(preset);
  return null;
}

function dmlScrgbColor(element: Element): string | null {
  if (element.getAttribute("r") == null || element.getAttribute("g") == null || element.getAttribute("b") == null) return null;
  const color = rgbToHex([
    dmlRound(dmlPercentage(element.getAttribute("r"), 0) * 255),
    dmlRound(dmlPercentage(element.getAttribute("g"), 0) * 255),
    dmlRound(dmlPercentage(element.getAttribute("b"), 0) * 255),
  ]);
  return dmlApplyLuminanceModifiers(color, element);
}

function dmlHslColor(element: Element): string | null {
  if (element.getAttribute("hue") == null || element.getAttribute("sat") == null || element.getAttribute("lum") == null) return null;
  const hue = (dmlFloat(element.getAttribute("hue"), 0) / 60000) % 360;
  const color = rgbToHex(hslToRgb(String(hue), dmlPercentage(element.getAttribute("sat"), 0), dmlPercentage(element.getAttribute("lum"), 0)));
  return dmlApplyLuminanceModifiers(color, element);
}

function dmlSchemeColor(element: Element): string | null {
  const colors: Record<string, string> = {
    accent1: "#4472c4",
    accent2: "#ed7d31",
    accent3: "#a5a5a5",
    accent4: "#ffc000",
    accent5: "#5b9bd5",
    accent6: "#70ad47",
    bg1: "#ffffff",
    bg2: "#e7e6e6",
    dk1: "#000000",
    dk2: "#44546a",
    folHlink: "#954f72",
    hlink: "#0563c1",
    lt1: "#ffffff",
    lt2: "#e7e6e6",
    tx1: "#000000",
    tx2: "#44546a",
  };
  const color = colors[element.getAttribute("val") || ""];
  return color ? dmlApplyLuminanceModifiers(color, element) : null;
}

function dmlPresetColor(element: Element): string | null {
  const colors: Record<string, string> = {
    dkBlue: "#00008b",
    dkCyan: "#008b8b",
    dkGoldenrod: "#b8860b",
    dkGray: "#a9a9a9",
    dkGreen: "#006400",
    dkGrey: "#a9a9a9",
    dkKhaki: "#bdb76b",
    dkMagenta: "#8b008b",
    dkOliveGreen: "#556b2f",
    dkOrange: "#ff8c00",
    dkOrchid: "#9932cc",
    dkRed: "#8b0000",
    dkSalmon: "#e9967a",
    dkSeaGreen: "#8fbc8f",
    dkSlateBlue: "#483d8b",
    dkSlateGray: "#2f4f4f",
    dkSlateGrey: "#2f4f4f",
    dkTurquoise: "#00ced1",
    dkViolet: "#9400d3",
    dkYellow: "#808000",
    ltBlue: "#add8e6",
    ltCoral: "#f08080",
    ltCyan: "#e0ffff",
    ltGoldenrodYellow: "#fafad2",
    ltGray: "#d3d3d3",
    ltGreen: "#90ee90",
    ltGrey: "#d3d3d3",
    ltPink: "#ffb6c1",
    ltSalmon: "#ffa07a",
    ltSeaGreen: "#20b2aa",
    ltSkyBlue: "#87cefa",
    ltSlateGray: "#778899",
    ltSlateGrey: "#778899",
    ltSteelBlue: "#b0c4de",
    ltYellow: "#ffffe0",
    medAquamarine: "#66cdaa",
    medBlue: "#0000cd",
    medOrchid: "#ba55d3",
    medPurple: "#9370db",
    medSeaGreen: "#3cb371",
    medSlateBlue: "#7b68ee",
    medSpringGreen: "#00fa9a",
    medTurquoise: "#48d1cc",
    medVioletRed: "#c71585",
    whiteSmoke: "#f5f5f5",
  };
  const value = element.getAttribute("val") || "";
  const color = colors[value] ?? parseCssColor(value.replace(/[A-Z]/g, (char) => char.toLowerCase()), {});
  return color ? dmlApplyLuminanceModifiers(color, element) : null;
}

function dmlHexColor(value: string | null): string | null {
  return value && /^[0-9a-f]{6}$/i.test(value) ? `#${value.toLowerCase()}` : null;
}

function dmlApplyLuminanceModifiers(color: string | null, element: Element): string | null {
  const parsed = hexToRgb(color || "");
  if (!parsed) return null;
  let rgb: [number, number, number] = parsed;
  const shade = childByLocal(element, "shade");
  if (shade?.getAttribute("val") != null) {
    const factor = dmlPercentage(shade.getAttribute("val"), 100000);
    rgb = rgb.map((channel) => dmlRound(channel * factor)) as [number, number, number];
  }
  const tint = childByLocal(element, "tint");
  if (tint?.getAttribute("val") != null) {
    const factor = dmlPercentage(tint.getAttribute("val"), 100000);
    rgb = rgb.map((channel) => dmlRound(channel + (255 - channel) * factor)) as [number, number, number];
  }
  const lumMod = childByLocal(element, "lumMod");
  if (lumMod?.getAttribute("val") != null) {
    const factor = dmlPercentage(lumMod.getAttribute("val"), 100000);
    rgb = rgb.map((channel) => dmlRound(channel * factor)) as [number, number, number];
  }
  const lumOff = childByLocal(element, "lumOff");
  if (lumOff?.getAttribute("val") != null) {
    const offset = dmlPercentage(lumOff.getAttribute("val"), 0);
    rgb = rgb.map((channel) => dmlRound(channel + (255 - channel) * offset)) as [number, number, number];
  }
  return rgbToHex(rgb);
}

function dmlRound(value: number): number {
  const floor = Math.floor(value);
  const fraction = value - floor;
  if (Math.abs(fraction - 0.5) < 1e-9) return floor % 2 === 0 ? floor : floor + 1;
  return Math.round(value);
}

function dmlPercentage(value: string | null, defaultValue: number): number {
  const parsed = dmlInt(value, defaultValue);
  return Number.isFinite(parsed) ? parsed / 100000 : defaultValue / 100000;
}

function dmlAlpha(parent: Element | null | undefined): number | null {
  if (!parent) return null;
  let result: number | null = null;
  const alpha = descendantsByLocal(parent, "alpha")[0];
  if (alpha?.getAttribute("val") != null) {
    const value = dmlInt(alpha.getAttribute("val"), Number.NaN);
    if (Number.isFinite(value)) result = value / 100000;
  }
  const alphaMod = descendantsByLocal(parent, "alphaMod")[0];
  if (alphaMod?.getAttribute("amt") != null) {
    const value = dmlInt(alphaMod.getAttribute("amt"), Number.NaN);
    if (Number.isFinite(value)) result = (result ?? 1) * (value / 100000);
  }
  return result;
}

function dmlInt(value: string | null, defaultValue: number): number {
  if (value == null) return defaultValue;
  if (!/^[+-]?\d+$/.test(value.trim())) return defaultValue;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

function dmlFloat(value: string | null, defaultValue: number): number {
  if (value == null) return defaultValue;
  if (value.trim() === "") return defaultValue;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : defaultValue;
}

function dmlText(element: Element): string {
  return descendantsByLocal(element, "t").map((node) => node.textContent || "").join("\n").trim();
}

type DmlTextRun = { text: string; attrs: string[]; breakBefore?: boolean };
type DmlTextLayout = { x: number; y: number; anchor: string | null; baseline: string | null; direction: string | null };
type DmlTextSvgOptions = { defaultBaseline?: string | null; defaultFill?: string | null; defaultStroke?: string | null; fallbackFill?: DmlPaint | null; fallbackStroke?: DmlStrokePaint | null; insetScaleX?: number; insetScaleY?: number };

function dmlTextSvg(element: Element, box: Box, options: DmlTextSvgOptions = {}): string {
  const runs = dmlTextRuns(element, options.fallbackFill, options.fallbackStroke).filter((run) => run.text);
  if (!runs.length) return "";
  const layout = dmlTextLayout(element, box, runs, options);
  const singleRunAttrs = runs.length === 1 ? runs[0]?.attrs ?? [] : [];
  const attrs = [
    `x="${formatNumber(layout.x)}"`,
    `y="${formatNumber(layout.y)}"`,
    options.defaultFill && !dmlAttrsInclude(singleRunAttrs, "fill") ? `fill="${options.defaultFill}"` : "",
    options.defaultStroke && !dmlAttrsInclude(singleRunAttrs, "stroke") ? `stroke="${options.defaultStroke}"` : "",
    layout.anchor ? `text-anchor="${layout.anchor}"` : "",
    layout.baseline ? `dominant-baseline="${layout.baseline}"` : "",
    layout.direction ? `direction="${layout.direction}"` : "",
    dmlTextWrap(element) === "none" ? `white-space="nowrap"` : "",
  ].filter(Boolean);
  if (runs.length === 1) {
    const run = runs[0];
    if (!run) return "";
    return `<text ${attrs.concat(dmlTextRunAttrsWithoutDefaults(run.attrs, options)).join(" ")}>${xml(run.text)}</text>`;
  }
  const x = formatNumber(layout.x);
  return `<text ${attrs.join(" ")}>${runs.map((run) => {
    const runAttrs = run.breakBefore ? [`x="${x}"`, 'dy="1.2em"', ...run.attrs] : run.attrs;
    return `<tspan${runAttrs.length ? ` ${runAttrs.join(" ")}` : ""}>${xml(run.text)}</tspan>`;
  }).join("")}</text>`;
}

function dmlTextRunAttrsWithoutDefaults(attrs: string[], options: DmlTextSvgOptions): string[] {
  return attrs.filter((attr) => {
    if (options.defaultFill && attr === `fill="${options.defaultFill}"`) return false;
    if (options.defaultStroke && attr === `stroke="${options.defaultStroke}"`) return false;
    return true;
  });
}

function dmlAttrsInclude(attrs: string[], name: string): boolean {
  return attrs.some((attr) => attr.startsWith(`${name}="`));
}

function dmlTextLayout(element: Element, box: Box, runs: DmlTextRun[], options: DmlTextSvgOptions = {}): DmlTextLayout {
  const [rawLeft, rawTop, rawRight, rawBottom] = dmlTextInsets(element);
  const left = rawLeft * (options.insetScaleX ?? 1);
  const right = rawRight * (options.insetScaleX ?? 1);
  const top = rawTop * (options.insetScaleY ?? 1);
  const bottom = rawBottom * (options.insetScaleY ?? 1);
  const inner = {
    x: box.x + left,
    y: box.y + top,
    width: Math.max(0, box.width - left - right),
    height: Math.max(0, box.height - top - bottom),
  };
  const anchor = dmlTextAnchor(element);
  const baseline = dmlTextBaseline(element) ?? options.defaultBaseline ?? null;
  const fontSize = dmlTextLayoutFontSize(runs) ?? inner.height / 1.4;
  return {
    x: anchor === "middle" ? inner.x + inner.width / 2 : anchor === "end" ? inner.x + inner.width : inner.x,
    y: baseline === "middle" ? inner.y + inner.height / 2 : baseline === "text-after-edge" ? inner.y + inner.height : inner.y + fontSize,
    anchor,
    baseline,
    direction: dmlTextDirection(element),
  };
}

function dmlTextInsets(element: Element): [number, number, number, number] {
  const bodyPr = descendantsByLocal(element, "bodyPr")[0];
  if (!bodyPr) return [0, 0, 0, 0];
  return [
    emuToPx(bodyPr.getAttribute("lIns")),
    emuToPx(bodyPr.getAttribute("tIns")),
    emuToPx(bodyPr.getAttribute("rIns")),
    emuToPx(bodyPr.getAttribute("bIns")),
  ];
}

function dmlTextLayoutFontSize(runs: DmlTextRun[]): number | null {
  for (const run of runs) {
    for (const attr of run.attrs) {
      const match = attr.match(/^font-size="([^"]+)"$/);
      if (match) return Number(match[1]);
    }
  }
  return null;
}

function dmlTextRuns(element: Element, fallbackFill: DmlPaint | null | undefined = null, fallbackStroke: DmlStrokePaint | null | undefined = null): DmlTextRun[] {
  const txBody = childByLocal(element, "txBody");
  const paragraphs = directChildrenByLocal(txBody, "p");
  const runs: DmlTextRun[] = [];
  for (const [paragraphIndex, paragraph] of paragraphs.entries()) {
    const paragraphRuns: DmlTextRun[] = [];
    const defRPr = dmlParagraphDefaultRunProperties(txBody, paragraph);
    const endParaRPr = childByLocal(paragraph, "endParaRPr");
    let pendingBreak = runs.length > 0;
    const firstRPr = dmlFirstParagraphRunProperties(paragraph);
    const bullet = dmlParagraphBullet(txBody, paragraph, paragraphIndex + 1);
    if (bullet) {
      paragraphRuns.push({
        text: `${bullet} `,
        attrs: dmlTextRunAttrsFromProperties([firstRPr, defRPr, endParaRPr], fallbackFill, fallbackStroke),
        breakBefore: pendingBreak,
      });
      pendingBreak = false;
    }
    let previousRPr = firstRPr;
    for (const child of Array.from(paragraph.children)) {
      const name = localName(child);
      if (name === "r" || name === "fld") {
        const rPr = childByLocal(child, "rPr");
        paragraphRuns.push({
          text: childByLocal(child, "t")?.textContent || "",
          attrs: dmlTextRunAttrsFromProperties([rPr, defRPr, endParaRPr], fallbackFill, fallbackStroke),
          breakBefore: pendingBreak,
        });
        pendingBreak = false;
        previousRPr = rPr;
      } else if (name === "br") {
        pendingBreak = true;
      } else if (name === "tab") {
        paragraphRuns.push({
          text: "\t",
          attrs: dmlTextRunAttrsFromProperties([previousRPr, defRPr, endParaRPr], fallbackFill, fallbackStroke),
          breakBefore: pendingBreak,
        });
        pendingBreak = false;
      }
    }
    runs.push(...paragraphRuns);
  }
  if (!runs.length) {
    const text = dmlText(element);
    if (text) runs.push({ text, attrs: [] });
  }
  return runs;
}

function dmlFirstParagraphRunProperties(paragraph: Element): Element | null {
  for (const child of Array.from(paragraph.children)) {
    if (["r", "fld"].includes(localName(child))) {
      const rPr = childByLocal(child, "rPr");
      if (rPr) return rPr;
    }
  }
  return null;
}

function dmlParagraphDefaultRunProperties(txBody: Element | null, paragraph: Element): Element | null {
  const pPr = childByLocal(paragraph, "pPr");
  const direct = childByLocal(pPr, "defRPr");
  if (direct) return direct;
  return childByLocal(dmlListStyleParagraphProperties(txBody, paragraph), "defRPr");
}

function dmlListStyleParagraphProperties(txBody: Element | null, paragraph: Element): Element | null {
  const pPr = childByLocal(paragraph, "pPr");
  const listStyle = childByLocal(txBody, "lstStyle");
  const level = dmlInt(pPr?.getAttribute("lvl") ?? null, 0) + 1 || 1;
  return childByLocal(listStyle, `lvl${Math.min(Math.max(level, 1), 9)}pPr`);
}

function dmlTextAnchor(element: Element): string | null {
  const pPr = dmlParagraphProperties(element, (item) => item.getAttribute("algn") != null);
  return ({ ctr: "middle", r: "end", l: "start" } as Record<string, string>)[pPr?.getAttribute("algn") || ""] ?? null;
}

function dmlTextDirection(element: Element): string | null {
  const pPr = dmlParagraphProperties(element, (item) => item.getAttribute("rtl") != null);
  return ["1", "true"].includes(pPr?.getAttribute("rtl") || "") ? "rtl" : null;
}

function dmlTextBaseline(element: Element): string | null {
  const anchor = descendantsByLocal(element, "bodyPr")[0]?.getAttribute("anchor") || "";
  return ({ ctr: "middle", b: "text-after-edge", t: "text-before-edge" } as Record<string, string>)[anchor] ?? null;
}

function dmlTextWrap(element: Element): string | null {
  return descendantsByLocal(element, "bodyPr")[0]?.getAttribute("wrap") === "none" ? "none" : null;
}

function dmlParagraphProperties(element: Element, predicate: (item: Element) => boolean): Element | null {
  const txBody = childByLocal(element, "txBody");
  const firstParagraph = directChildrenByLocal(txBody, "p")[0] ?? null;
  const pPr = childByLocal(firstParagraph, "pPr") ?? descendantsByLocal(element, "pPr")[0] ?? null;
  if (pPr && predicate(pPr)) return pPr;
  const listPPr = firstParagraph ? dmlListStyleParagraphProperties(txBody, firstParagraph) : null;
  return listPPr && predicate(listPPr) ? listPPr : null;
}

function dmlParagraphBullet(txBody: Element | null, paragraph: Element, number: number): string | null {
  const pPr = childByLocal(paragraph, "pPr");
  if (childByLocal(pPr, "buNone")) return null;
  const directChar = childByLocal(pPr, "buChar")?.getAttribute("char");
  if (directChar) return directChar;
  const directAuto = childByLocal(pPr, "buAutoNum");
  if (directAuto) return dmlAutoNumberBullet(directAuto, number);
  const listPPr = dmlListStyleParagraphProperties(txBody, paragraph);
  if (childByLocal(listPPr, "buNone")) return null;
  const listChar = childByLocal(listPPr, "buChar")?.getAttribute("char");
  if (listChar) return listChar;
  return dmlAutoNumberBullet(childByLocal(listPPr, "buAutoNum"), number);
}

function dmlAutoNumberBullet(element: Element | null, number: number): string | null {
  if (!element) return null;
  const value = (dmlInt(element.getAttribute("startAt"), 0) || 1) + number - 1;
  const lowerAlpha = alphaNumber(value);
  const upperAlpha = lowerAlpha.toUpperCase();
  const lowerRoman = romanNumber(value);
  const upperRoman = lowerRoman.toUpperCase();
  return ({
    arabicPeriod: `${value}.`,
    arabicParenR: `${value})`,
    arabicParenBoth: `(${value})`,
    arabicPlain: String(value),
    alphaLcPeriod: `${lowerAlpha}.`,
    alphaUcPeriod: `${upperAlpha}.`,
    alphaLcParenR: `${lowerAlpha})`,
    alphaUcParenR: `${upperAlpha})`,
    alphaLcParenBoth: `(${lowerAlpha})`,
    alphaUcParenBoth: `(${upperAlpha})`,
    romanLcPeriod: `${lowerRoman}.`,
    romanUcPeriod: `${upperRoman}.`,
    romanLcParenR: `${lowerRoman})`,
    romanUcParenR: `${upperRoman})`,
    romanLcParenBoth: `(${lowerRoman})`,
    romanUcParenBoth: `(${upperRoman})`,
  } as Record<string, string>)[element.getAttribute("type") || ""] ?? `${value}.`;
}

function alphaNumber(value: number): string {
  if (value <= 0) return String(value);
  const letters: string[] = [];
  let current = value;
  while (current > 0) {
    current -= 1;
    letters.unshift(String.fromCharCode("a".charCodeAt(0) + (current % 26)));
    current = Math.floor(current / 26);
  }
  return letters.join("");
}

function romanNumber(value: number): string {
  if (value <= 0 || value > 3999) return String(value);
  const pairs: Array<[number, string]> = [[1000, "m"], [900, "cm"], [500, "d"], [400, "cd"], [100, "c"], [90, "xc"], [50, "l"], [40, "xl"], [10, "x"], [9, "ix"], [5, "v"], [4, "iv"], [1, "i"]];
  let current = value;
  let result = "";
  for (const [amount, token] of pairs) {
    while (current >= amount) {
      result += token;
      current -= amount;
    }
  }
  return result;
}

function dmlTextRunAttrs(...properties: Array<Element | null>): string[] {
  const candidates = properties.filter((item): item is Element => Boolean(item));
  return dmlTextRunAttrsFromCandidates(candidates, null, null);
}

function dmlTextRunAttrsFromProperties(properties: Array<Element | null>, fallbackFill: DmlPaint | null | undefined, fallbackStroke: DmlStrokePaint | null | undefined): string[] {
  const candidates = properties.filter((item): item is Element => Boolean(item));
  return dmlTextRunAttrsFromCandidates(candidates, fallbackFill, fallbackStroke);
}

function dmlTextRunAttrsFromCandidates(candidates: Element[], fallbackFill: DmlPaint | null | undefined, fallbackStroke: DmlStrokePaint | null | undefined): string[] {
  if (!candidates.length) return [...dmlPaintFillAttrs(fallbackFill), ...dmlStrokeAttrs(fallbackStroke)];
  const attrs: string[] = [];
  const fontSize = dmlInt(dmlFirstTextAttr(candidates, "sz"), 0);
  if (fontSize > 0) attrs.push(`font-size="${formatNumber(fontSize / 100)}"`);
  if (dmlBool(dmlFirstTextAttr(candidates, "b"))) attrs.push('font-weight="bold"');
  if (dmlBool(dmlFirstTextAttr(candidates, "i"))) attrs.push('font-style="italic"');
  const cap = dmlFirstTextAttr(candidates, "cap");
  if (cap === "small") attrs.push('font-variant="small-caps"');
  if (cap === "all") attrs.push('font-variant="all-small-caps"');
  const typeface = dmlTextTypeface(candidates);
  if (typeface) attrs.push(`font-family="${xml(typeface)}"`);
  attrs.push(...dmlTextFillAttrs(candidates, fallbackFill));
  attrs.push(...dmlTextOutlineAttrs(dmlFirstTextChild(candidates, "ln"), fallbackStroke));
  const decoration = dmlTextDecoration(candidates);
  if (decoration) attrs.push(`text-decoration="${decoration}"`);
  attrs.push(...dmlTextDecorationDetailAttrs(candidates, decoration));
  const baseline = dmlInt(dmlFirstTextAttr(candidates, "baseline"), 0);
  const baselineShift = dmlBaselineShift(baseline);
  if (baselineShift) attrs.push(`baseline-shift="${baselineShift}"`);
  const spacing = dmlInt(dmlFirstTextAttr(candidates, "spc"), 0);
  if (spacing) attrs.push(`letter-spacing="${formatNumber(spacing / 75)}"`);
  return attrs;
}

function dmlBaselineShift(value: number): string | null {
  if (value >= 30000) return "super";
  if (value <= -25000) return "sub";
  return null;
}

function dmlFirstTextAttr(candidates: Element[], name: string): string | null {
  for (const candidate of candidates) {
    const value = candidate.getAttribute(name);
    if (value != null) return value;
  }
  return null;
}

function dmlFirstTextChild(candidates: Element[], name: string): Element | null {
  for (const candidate of candidates) {
    const child = childByLocal(candidate, name);
    if (child) return child;
  }
  return null;
}

function dmlTextTypeface(candidates: Element[]): string | null {
  for (const candidate of candidates) {
    for (const name of ["latin", "ea", "cs", "sym"]) {
      const typeface = childByLocal(candidate, name)?.getAttribute("typeface");
      if (typeface) return typeface;
    }
  }
  return null;
}

function dmlTextFillAttrs(candidates: Element[], fallbackFill: DmlPaint | null | undefined = null): string[] {
  const source = candidates.find((candidate) => childByLocal(candidate, "noFill") || dmlFillPaint(candidate));
  if (!source) return dmlPaintFillAttrs(fallbackFill);
  if (childByLocal(source, "noFill")) return ['fill="none"'];
  const paint = dmlFillPaint(source);
  return dmlPaintFillAttrs(paint);
}

function dmlPaintFillAttrs(paint: DmlPaint | null | undefined): string[] {
  if (!paint) return [];
  return [
    paint.color ? `fill="${paint.color}"` : "",
    paint.alpha != null && paint.alpha < 1 ? `fill-opacity="${formatNumber(paint.alpha)}"` : "",
  ].filter(Boolean);
}

function dmlTextOutlineAttrs(ln: Element | null, fallbackStroke: DmlStrokePaint | null | undefined = null): string[] {
  if (!ln) return dmlStrokeAttrs(fallbackStroke);
  if (childByLocal(ln, "noFill")) return [];
  const paint = dmlFillPaint(ln);
  const strokeWidth = emuToPx(ln.getAttribute("w"));
  return dmlStrokeAttrs({
    color: paint?.color ?? null,
    alpha: paint?.alpha ?? null,
    width: strokeWidth,
    lineCap: dmlLineCap(ln.getAttribute("cap")),
    lineJoin: dmlLineJoin(ln),
    dasharray: dmlDasharray(ln, strokeWidth),
    miterlimit: dmlMiterlimit(ln),
  });
}

function dmlStrokeAttrs(paint: DmlStrokePaint | null | undefined): string[] {
  if (!paint?.color) return [];
  return [
    `stroke="${paint.color}"`,
    paint.alpha != null && paint.alpha < 1 ? `stroke-opacity="${formatNumber(paint.alpha)}"` : "",
    paint.width ? `stroke-width="${formatNumber(paint.width)}"` : "",
    paint.lineCap ? `stroke-linecap="${paint.lineCap}"` : "",
    paint.lineJoin ? `stroke-linejoin="${paint.lineJoin}"` : "",
    paint.dasharray ? `stroke-dasharray="${paint.dasharray}"` : "",
    paint.miterlimit != null ? `stroke-miterlimit="${formatNumber(paint.miterlimit)}"` : "",
  ].filter(Boolean);
}

function dmlTextDecoration(candidates: Element[]): string | null {
  const values: string[] = [];
  const underline = dmlFirstTextAttr(candidates, "u");
  const strike = dmlFirstTextAttr(candidates, "strike");
  if (underline && underline !== "none") values.push("underline");
  if (strike && strike !== "noStrike") values.push("line-through");
  return values.length ? values.join(" ") : null;
}

function dmlTextDecorationDetailAttrs(candidates: Element[], decoration: string | null): string[] {
  if (!decoration?.split(/\s+/).includes("underline")) return [];
  const u = dmlFirstTextAttr(candidates, "u") || "";
  const uFill = dmlFirstTextChild(candidates, "uFill");
  const uLn = dmlFirstTextChild(candidates, "uLn");
  const paint = uFill ? dmlFillPaint(uFill) : null;
  const thickness = uLn ? emuToPx(uLn.getAttribute("w")) : 0;
  return [
    dmlTextDecorationStyle(u) ? `text-decoration-style="${dmlTextDecorationStyle(u)}"` : "",
    paint?.color ? `text-decoration-color="${dmlColorWithAlpha(paint.color, paint.alpha)}"` : "",
    thickness ? `text-decoration-thickness="${formatNumber(thickness)}"` : "",
  ].filter(Boolean);
}

function dmlTextDecorationStyle(value: string): string | null {
  return ({
    dash: "dashed",
    dashHeavy: "dashed",
    dbl: "double",
    dotted: "dotted",
    dottedHeavy: "dotted",
    wavy: "wavy",
    wavyDbl: "wavy",
    wavyHeavy: "wavy",
  } as Record<string, string>)[value] ?? null;
}

function dmlColorWithAlpha(color: string, alpha: number | null): string {
  if (alpha == null || alpha >= 1) return color;
  const rgb = hexToRgb(color);
  if (!rgb) return color;
  const suffix = clamp(Math.round(alpha * 255), 0, 255).toString(16).padStart(2, "0");
  return `${rgbToHex(rgb)}${suffix}`;
}

function dmlFlip(spPr: Element, name: "flipH" | "flipV"): boolean {
  return dmlBool(childByLocal(spPr, "xfrm")?.getAttribute(name) ?? null);
}

function dmlSvgId(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "dml-shape";
}

function childByLocal(element: Element | null | undefined, name: string): Element | null {
  return element ? Array.from(element.children).find((child) => localName(child) === name) ?? null : null;
}

function directChildrenByLocal(element: Element | null | undefined, name: string): Element[] {
  return element ? Array.from(element.children).filter((child) => localName(child) === name) : [];
}

function descendantsByLocal(element: Element, name: string): Element[] {
  const result: Element[] = [];
  const visit = (current: Element): void => {
    for (const child of Array.from(current.children)) {
      if (localName(child) === name) result.push(child);
      visit(child);
    }
  };
  visit(element);
  return result;
}

function emuToPx(value: string | null | undefined): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed / emuPerPx : 0;
}

const coverageSupportedElements = new Set([
  "a",
  "circle",
  "ellipse",
  "foreignObject",
  "g",
  "image",
  "line",
  "path",
  "polygon",
  "polyline",
  "rect",
  "style",
  "svg",
  "switch",
  "symbol",
  "text",
  "tspan",
  "use",
]);

const coverageIgnoredElements = new Set(["defs", "desc", "linearGradient", "metadata", "pattern", "radialGradient", "stop", "title"]);

const coverageRenderingElements = new Set(["circle", "ellipse", "image", "line", "path", "polygon", "polyline", "rect", "text", "tspan"]);

const coverageUnsupportedAttributes = new Set([
  "alignment-baseline",
  "baseline-shift",
  "clip-path",
  "clip-rule",
  "color-rendering",
  "direction",
  "dominant-baseline",
  "fill-rule",
  "filter",
  "font-feature-settings",
  "font-kerning",
  "font-size-adjust",
  "font-stretch",
  "font-variant",
  "font-variation-settings",
  "glyph-orientation-horizontal",
  "glyph-orientation-vertical",
  "gradientTransform",
  "gradientUnits",
  "image-rendering",
  "isolation",
  "kerning",
  "letter-spacing",
  "lengthAdjust",
  "marker",
  "marker-end",
  "marker-mid",
  "marker-start",
  "mask",
  "mix-blend-mode",
  "opacity",
  "overflow",
  "paint-order",
  "pathLength",
  "preserveAspectRatio",
  "rotate",
  "shape-rendering",
  "spreadMethod",
  "stroke-dashoffset",
  "stroke-linecap",
  "stroke-linejoin",
  "textLength",
  "text-decoration",
  "text-decoration-color",
  "text-decoration-line",
  "text-decoration-skip-ink",
  "text-decoration-style",
  "text-decoration-thickness",
  "text-orientation",
  "text-rendering",
  "text-transform",
  "text-underline-offset",
  "transform-origin",
  "unicode-bidi",
  "vector-effect",
  "word-spacing",
  "writing-mode",
]);

const coverageTextLayoutAttributes = new Set([
  "alignment-baseline",
  "baseline-shift",
  "direction",
  "font-feature-settings",
  "font-kerning",
  "font-size-adjust",
  "font-stretch",
  "font-variant",
  "font-variation-settings",
  "glyph-orientation-horizontal",
  "glyph-orientation-vertical",
  "kerning",
  "lengthAdjust",
  "letter-spacing",
  "rotate",
  "text-decoration",
  "text-decoration-color",
  "text-decoration-line",
  "text-decoration-skip-ink",
  "text-decoration-style",
  "text-decoration-thickness",
  "text-orientation",
  "text-transform",
  "text-underline-offset",
  "textLength",
  "unicode-bidi",
  "word-spacing",
  "writing-mode",
]);

const coverageSupportedPathCommands = new Set(["M", "L", "H", "V", "C", "S", "Q", "T", "A", "Z"]);

function analyzeSvgCoverage(root: Element): SvgCoverage {
  const stats: SvgCoverage = {
    total_elements: 0,
    convertible_elements: 0,
    ignored_elements: 0,
    unsupported_elements: {},
    unsupported_attributes: {},
    unsupported_path_commands: {},
    estimated_element_coverage: 1,
  };
  const css = collectCss(root);
  const refs = collectRefs(root);
  const viewport = svgViewport(root);
  const walk = (element: Element, inheritedStyle: SvgStyle, currentViewport: Viewport, inDefs = false) => {
    const tag = localName(element);
    stats.total_elements += 1;
    const style = computedStyle(element, inheritedStyle, css, refs, currentViewport);
    const ignored = coverageElementIsIgnored(element, tag, style, refs, css, currentViewport, inDefs);
    const supportedElement = coverageElementIsSupported(element, tag, refs, css, style, currentViewport);
    if (ignored) {
      stats.ignored_elements += 1;
    } else if (coverageSupportedElements.has(tag) && supportedElement) {
      stats.convertible_elements += 1;
    } else if (coverageSupportedElements.has(tag)) {
      addCoverageCount(stats.unsupported_elements, coverageSupportedElementIssue(tag));
    } else {
      addCoverageCount(stats.unsupported_elements, tag);
    }
    if (!ignored) inspectCoverageAttributes(element, style, tag, stats, refs, css, currentViewport);
    if (tag === "foreignObject") return;
    const childViewport = tag === "svg" ? renderedSvgViewport(element, currentViewport, css, style) : currentViewport;
    for (const child of Array.from(element.children)) walk(child, style, childViewport, inDefs || tag === "defs");
  };
  walk(root, {}, viewport);
  inspectReferencedPaintServerAttributes(root, refs, css, viewport, stats);
  const measurable = Math.max(stats.total_elements - stats.ignored_elements, 0);
  stats.estimated_element_coverage = measurable ? Math.round((stats.convertible_elements / measurable) * 10000) / 10000 : 1;
  stats.unsupported_elements = sortedCoverageCounts(stats.unsupported_elements);
  stats.unsupported_attributes = sortedCoverageCounts(stats.unsupported_attributes);
  stats.unsupported_path_commands = sortedCoverageCounts(stats.unsupported_path_commands);
  return stats;
}

function coverageElementIsSupported(element: Element, tag: string, refs: Map<string, Element>, css: CssRule[] = [], style: SvgStyle = {}, viewport: Viewport = defaultViewport()): boolean {
  if (tag === "path") return parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]) != null;
  if (tag === "polygon" || tag === "polyline") return parsePoints(element.getAttribute("points") || "").length >= 2;
  if (tag === "image") return supportedDataImage(hrefValue(element));
  if (tag === "use") {
    const href = hrefValue(element);
    if (!href.startsWith("#") || !refs.has(href.slice(1))) return false;
    return coverageUseReferenceIsSupported(element, style, refs, css, viewport);
  }
  if (tag === "foreignObject") return Array.from(element.querySelectorAll("table")).some((item) => localName(item) === "table" && htmlTableGrid(item) != null);
  if (tag === "switch") return switchSelectedChild(element) != null || element.children.length === 0;
  return true;
}

function coverageUseReferenceIsSupported(element: Element, inheritedStyle: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  const href = hrefValue(element);
  const refId = href.startsWith("#") ? href.slice(1) : "";
  const ref = refId ? refs.get(refId) : null;
  if (!ref || refStack.has(refId)) return false;
  const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, inheritedStyle) : viewport;
  return coverageReferencedSubtreeIsSupported(ref, inheritedStyle, refs, css, refViewport, new Set([...refStack, refId]));
}

function coverageReferencedSubtreeIsSupported(element: Element, inheritedStyle: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string>): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (coverageElementIsIgnored(element, tag, style, refs, css, viewport, coverageIgnoredElements.has(tag))) return true;
  if (tag === "use") return coverageUseReferenceIsSupported(element, style, refs, css, viewport, refStack);
  if (tag === "path" && parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]) == null) return false;
  if ((tag === "polygon" || tag === "polyline") && parsePoints(element.getAttribute("points") || "").length < 2) return false;
  if (tag === "image" && !supportedDataImage(hrefValue(element))) return false;
  if (tag === "foreignObject" && !Array.from(element.querySelectorAll("table")).some((item) => localName(item) === "table")) return false;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    if (!selected) return element.children.length === 0;
    return coverageReferencedSubtreeIsSupported(selected, style, refs, css, viewport, refStack);
  }
  if (!coverageSupportedElements.has(tag) && !coverageIgnoredElements.has(tag)) return false;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  return Array.from(element.children).every((child) => coverageReferencedSubtreeIsSupported(child, style, refs, css, childViewport, refStack));
}

function coverageElementIsIgnored(element: Element, tag: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, inDefs: boolean): boolean {
  return (
    inDefs ||
    coverageIgnoredElements.has(tag) ||
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.visibility === "collapse" ||
    coverageHasNonRenderingGeometry(element, tag, style, css, viewport) ||
    coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport)
  );
}

function coverageHasNonRenderingGeometry(element: Element, tag: string, style: SvgStyle, css: CssRule[], viewport: Viewport): boolean {
  const declarations = resolvedCascadedDeclarations(element, css, style);
  if (tag === "foreignObject" || tag === "rect" || tag === "image") return cascadedGeom(element, declarations, "width", "x", viewport) <= 0 || cascadedGeom(element, declarations, "height", "y", viewport) <= 0;
  if (tag === "circle") return cascadedGeom(element, declarations, "r", "diag", viewport) <= 0;
  if (tag === "ellipse") return cascadedGeom(element, declarations, "rx", "x", viewport) <= 0 || cascadedGeom(element, declarations, "ry", "y", viewport) <= 0;
  return false;
}

function coverageHasNoVisiblePaint(element: Element, tag: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  if (tag === "image") return style.imageAlpha === 0;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return !coverageSubtreeHasVisibleRendering(ref, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (!["circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text", "tspan"].includes(tag)) return false;
  if ((tag === "text" || tag === "tspan") && !(element.textContent || "").trim()) return true;
  const hasFill = tag !== "line" && style.fill !== "none" && style.fillAlpha !== 0;
  const hasStroke = !!style.stroke && style.stroke !== "none" && style.strokeAlpha !== 0 && (style.strokeWidth ?? 1) > 0;
  return !(hasFill || hasStroke);
}

function coverageSubtreeHasVisibleRendering(element: Element, inheritedStyle: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string>): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none") return false;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return coverageSubtreeHasVisibleRendering(ref, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && coverageRenderingElements.has(tag) && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport) && !coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport, refStack)) return true;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? coverageSubtreeHasVisibleRendering(selected, style, refs, css, childViewport, refStack) : false;
  }
  return Array.from(element.children).some((child) => coverageSubtreeHasVisibleRendering(child, style, refs, css, childViewport, refStack));
}

function coverageSupportedElementIssue(tag: string): string {
  if (tag === "path") return "path:unsupported-command";
  if (tag === "polygon" || tag === "polyline") return `${tag}:invalid-points`;
  if (tag === "image") return "image:unsupported-reference";
  if (tag === "use") return "use:unsupported-reference";
  if (tag === "foreignObject") return "foreignObject:unsupported-content";
  if (tag === "switch") return "switch:unsupported-branch";
  return tag;
}

function inspectCoverageAttributes(element: Element, style: SvgStyle, tag: string, stats: SvgCoverage, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): void {
  const attributes = { ...attrs(element), ...resolvedCascadedDeclarations(element, css, style) };
  for (const [name, value] of Object.entries(attributes)) {
    if (!coverageUnsupportedAttributes.has(name)) continue;
    if (coverageTextLayoutAttributes.has(name) && !subtreeHasVisibleText(element, style, css, refs, viewport)) continue;
    if (coverageAttributeIsSupportedOrNoop(element, tag, name, value, style, refs, css, viewport)) continue;
    addCoverageCount(stats.unsupported_attributes, name);
  }
  inspectCoverageTspanRunAttributes(element, style, tag, stats, refs, css, viewport);
  inspectCoverageHref(element, tag, stats, refs);
  inspectCoveragePaintServers(element, style, tag, stats, refs, css);
  if (tag === "use") inspectCoverageUseReference(element, style, stats, refs, css, viewport, refStack);
  if (tag === "path") {
    for (const command of unsupportedPathCommands(element.getAttribute("d") || "")) addCoverageCount(stats.unsupported_path_commands, command);
  }
}

function inspectCoverageHref(element: Element, tag: string, stats: SvgCoverage, refs: Map<string, Element>): void {
  const href = hrefValue(element);
  if (tag === "image" && !supportedDataImage(href)) addCoverageCount(stats.unsupported_attributes, "href");
  if (tag === "use" && (!href.startsWith("#") || !refs.has(href.slice(1)))) addCoverageCount(stats.unsupported_attributes, "href");
}

function inspectCoveragePaintServers(element: Element, style: SvgStyle, tag: string, stats: SvgCoverage, refs: Map<string, Element>, css: CssRule[]): void {
  const declarations = resolvedCascadedDeclarations(element, css, style);
  for (const attr of ["fill", "stroke"] as const) {
    const value = declarations[attr] ?? element.getAttribute(attr);
    if (!value || !coveragePaintChannelIsVisible(tag, attr, style)) continue;
    const ref = paintUrlRef(value.trim());
    if (!ref || ref.fallback) continue;
    const server = refs.get(ref.id);
    const serverTag = server ? localName(server) : "";
    if (serverTag === "pattern") {
      if (!paintServerColor(ref.id, refs, style, new Set(), css)) addCoverageCount(stats.unsupported_attributes, `${attr}:pattern`);
    } else if (serverTag === "linearGradient" || serverTag === "radialGradient") {
      if (!paintServerColor(ref.id, refs, style, new Set(), css)) addCoverageCount(stats.unsupported_attributes, `${attr}:paint-server`);
    } else {
      addCoverageCount(stats.unsupported_attributes, `${attr}:paint-server`);
    }
  }
}

function inspectReferencedPaintServerAttributes(root: Element, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, stats: SvgCoverage): void {
  for (const [id, server] of refs.entries()) {
    const tag = localName(server);
    if (tag !== "linearGradient" && tag !== "radialGradient") continue;
    if (!subtreeReferencesPaintServer(root, id, css, refs, {}, viewport, new Set())) continue;
    const href = hrefValue(server);
    if (hasHrefAttribute(server) && (!href.startsWith("#") || !refs.has(href.slice(1)))) addCoverageCount(stats.unsupported_attributes, "href");
    if (paintServerColor(id, refs, {}, new Set(), css)) continue;
    if (server.hasAttribute("gradientTransform")) addCoverageCount(stats.unsupported_attributes, "gradientTransform");
    if (server.hasAttribute("gradientUnits")) addCoverageCount(stats.unsupported_attributes, "gradientUnits");
    if (server.hasAttribute("spreadMethod")) addCoverageCount(stats.unsupported_attributes, "spreadMethod");
  }
}

function subtreeReferencesPaintServer(element: Element, paintServerId: string, css: CssRule[], refs: Map<string, Element>, inheritedStyle: SvgStyle, viewport: Viewport, refStack: Set<string>): boolean {
  const tag = localName(element);
  if (tag === "defs") return false;
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none") return false;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeReferencesPaintServer(ref, paintServerId, css, refs, style, refViewport, new Set([...refStack, refId]));
  }
  if (!["linearGradient", "pattern", "radialGradient", "stop"].includes(tag) && style.visibility !== "hidden" && style.visibility !== "collapse" && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport)) {
    for (const attr of ["fill", "stroke"] as const) {
      const ref = paintUrlRef(style[attr] || "");
      if (ref?.id === paintServerId && !ref.fallback && coveragePaintChannelIsVisible(tag, attr, style)) return true;
    }
  }
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeReferencesPaintServer(selected, paintServerId, css, refs, style, childViewport, refStack) : false;
  }
  return Array.from(element.children).some((child) => subtreeReferencesPaintServer(child, paintServerId, css, refs, style, childViewport, refStack));
}

function inspectCoverageUseReference(element: Element, inheritedStyle: SvgStyle, stats: SvgCoverage, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string>): void {
  const href = hrefValue(element);
  const refId = href.startsWith("#") ? href.slice(1) : "";
  const ref = refId ? refs.get(refId) : null;
  if (!ref || refStack.has(refId)) return;
  let refViewport = viewport;
  if (["svg", "symbol"].includes(localName(ref))) refViewport = useViewport(ref, element, viewport, css, inheritedStyle);
  inspectCoverageReferencedSubtree(ref, inheritedStyle, stats, refs, css, refViewport, new Set([...refStack, refId]));
}

function inspectCoverageReferencedSubtree(element: Element, inheritedStyle: SvgStyle, stats: SvgCoverage, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string>): void {
  const tag = localName(element);
  if (coverageIgnoredElements.has(tag)) return;
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none") return;
  if (coverageHasNonRenderingGeometry(element, tag, style, css, viewport)) return;
  if (coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport, refStack) && !coverageHasUnresolvedPaintServer(style, refs, css)) return;
  const visibilityHidden = style.visibility === "hidden" || style.visibility === "collapse";
  if (!visibilityHidden) inspectCoverageAttributes(element, style, tag, stats, refs, css, viewport, refStack);
  if (tag === "foreignObject") return;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    if (selected) inspectCoverageReferencedSubtree(selected, style, stats, refs, css, childViewport, refStack);
    return;
  }
  for (const child of Array.from(element.children)) inspectCoverageReferencedSubtree(child, style, stats, refs, css, childViewport, refStack);
}

function coveragePaintChannelIsVisible(tag: string, attr: "fill" | "stroke", style: SvgStyle): boolean {
  if (attr === "fill") {
    if (!["circle", "ellipse", "path", "polygon", "polyline", "rect", "text", "tspan", "use"].includes(tag)) return false;
    return style.fillAlpha !== 0;
  }
  if (!["circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text", "tspan", "use"].includes(tag)) return false;
  return style.strokeAlpha !== 0 && (style.strokeWidth ?? 1) !== 0;
}

function coverageHasUnresolvedPaintServer(style: SvgStyle, refs: Map<string, Element>, css: CssRule[]): boolean {
  for (const attr of ["fill", "stroke"] as const) {
    const value = style[attr];
    if (!value) continue;
    const ref = paintUrlRef(value);
    if (ref && !ref.fallback && !paintServerColor(ref.id, refs, style, new Set(), css)) return true;
  }
  return false;
}

function subtreeHasVisibleText(element: Element, inheritedStyle: SvgStyle, css: CssRule[], refs: Map<string, Element>, viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") return false;
  if ((tag === "text" || tag === "tspan") && (element.textContent || "").trim() && !coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport, refStack)) return true;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeHasVisibleText(ref, style, css, refs, refViewport, new Set([...refStack, refId]));
  }
  if (tag === "foreignObject") return !!element.textContent?.trim();
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeHasVisibleText(selected, style, css, refs, childViewport, refStack) : false;
  }
  return Array.from(element.children).some((child) => subtreeHasVisibleText(child, style, css, refs, childViewport, refStack));
}

function coverageAttributeIsSupportedOrNoop(element: Element, tag: string, name: string, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized || coverageAttributeHasNoEffect(element, name, value)) return true;
  if (["clip-path", "filter", "isolation", "mask", "mix-blend-mode"].includes(name) && !coverageSubtreeHasVisibleRendering(element, style, refs, css, viewport, new Set())) return true;
  if (name === "clip-path") return clipPathIsSupportedOrNoop(element, tag, value, style, refs, css, viewport);
  if (name === "clip-rule") return clipRuleHasNoEffect(element);
  if (name === "fill-rule") return !subtreeHasVisibleFill(element, style, refs, css, viewport);
  if (name === "isolation") return isolationIsRedundantWithBlend(element, tag, normalized, style, css, refs, viewport);
  if (name === "direction") return normalized === "ltr" || (tag === "text" && normalizeTextDirection(value) != null);
  if (name === "dominant-baseline" || name === "alignment-baseline") return ["auto", "baseline", "alphabetic"].includes(normalized) || (tag === "text" && normalizeTextBaseline(value) != null) || firstPositionedTspanBaselineIsSupported(element, name, value);
  if (name === "baseline-shift") return zeroLengthOrPercentage(value) || normalizeBaselineShift(value) != null;
  if (name === "font-stretch") return parseCssLength(value, 100, Number.NaN) === 100;
  if (name === "font-variant") return normalizeFontVariant(value) != null;
  if (name === "glyph-orientation-horizontal" || name === "glyph-orientation-vertical") return zeroAngle(value);
  if (name === "kerning") return zeroLengthOrPercentage(value) || textHasNoKerningPairs(element);
  if (name === "font-kerning") return normalized === "none" && textHasNoKerningPairs(element);
  if (name === "letter-spacing") return normalizeSpacingLength(value, style.fontSize ?? rootFontSize) != null;
  if (name === "lengthAdjust") return normalizeLengthAdjust(value) != null;
  if (name === "marker" || name === "marker-start" || name === "marker-end") return markerAttributeIsSupportedOrNoop(element, name, value, style, refs, css, viewport);
  if (name === "marker-mid") return subtreeMarkerMidHasNoEffect(element, style, refs, css, viewport);
  if (name === "overflow") return overflowIsSupportedOrNoop(element, tag, value, style, refs, css, viewport);
  if (name === "opacity") return opacityIsSupportedOrNoop(element, tag, value, style, refs, css, viewport);
  if (name === "paint-order") return paintOrderHasNoEffect(tag, value, style);
  if (name === "pathLength") return pathLengthIsSupportedOrNoop(element, tag, value, style, viewport, css);
  if (name === "preserveAspectRatio") return preserveAspectRatioIsSupportedOrNoop(element, tag, value, refs);
  if (name === "rotate") return singleTextRotation(value, element.textContent || null) != null;
  if (name === "stroke-dashoffset") return strokeDashoffsetHasNoEffect(value, style, viewport) || strokeDashoffsetIsSupported(value, style, viewport);
  if (name === "stroke-linecap" || name === "stroke-linejoin") return !subtreeHasUnsupportedStrokeLineEnum(element, style, refs, css, viewport, name);
  if (name === "textLength") return textLengthIsSupported(element, tag, value, style);
  if (name === "text-decoration") return textDecorationShorthandIsSupported(value, style, viewport);
  if (name === "text-decoration-line") return hasSupportedTextDecorationLine(value);
  if (name === "text-decoration-style") return textDecorationStyleIsSupportedOrNoop(value, style);
  if (name === "text-decoration-color") return textDecorationColorHasNoEffect(value, style);
  if (name === "text-decoration-thickness") return textDecorationThicknessHasNoEffect(value, style, viewport);
  if (name === "text-decoration-skip-ink" || name === "text-underline-offset") return !hasUnderline(style) || normalized === "auto";
  if (name === "text-orientation") return normalized === "mixed";
  if (name === "text-transform") return normalizeTextTransform(value) != null;
  if (name === "transform-origin") return transformOriginIsSupportedOrNoop(element, value, style, refs, css, viewport);
  if (name === "unicode-bidi") return normalized === "normal";
  if (name === "vector-effect") return vectorEffectIsSupportedOrNoop(element, value, style, refs, css, viewport);
  if (name === "word-spacing") return wordSpacingHasNoEffect(element, tag, value) || wordSpacingIsSupported(element, tag, value, style);
  if (name === "writing-mode") return ["horizontal-tb", "lr", "lr-tb", "rl", "rl-tb"].includes(normalized);
  return false;
}

function coverageAttributeHasNoEffect(element: Element, name: string, value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return true;
  if (["color-rendering", "image-rendering", "shape-rendering", "text-rendering"].includes(name)) return renderingQualityHintHasNoEffect(normalized);
  if (["clip-path", "filter", "mask"].includes(name)) return normalized === "none";
  if (["clip-rule", "fill-rule"].includes(name)) return normalized === "nonzero";
  if (name === "isolation") return normalized === "auto";
  if (name === "mix-blend-mode") return normalized === "normal";
  if (name === "paint-order") return normalized === "normal";
  if (["marker", "marker-start", "marker-mid", "marker-end"].includes(name)) return normalized === "none";
  if (name === "font-feature-settings" || name === "font-variation-settings") return normalized === "normal" || normalized === "none";
  if (name === "font-size-adjust") return normalized === "normal" || normalized === "none";
  if (name === "font-kerning") return normalized === "auto" || normalized === "normal";
  if (name === "font-stretch") return normalized === "normal";
  if (name === "glyph-orientation-horizontal" || name === "glyph-orientation-vertical") return normalized === "auto";
  if (name === "kerning") return normalized === "auto" || normalized === "normal";
  if (name === "baseline-shift") return normalized === "baseline";
  if (name === "direction") return normalized === "ltr";
  if (name === "unicode-bidi") return normalized === "normal";
  if (name === "writing-mode") return normalized === "horizontal-tb";
  if (name === "text-orientation") return normalized === "mixed";
  if (name === "text-decoration-thickness" || name === "text-decoration-skip-ink" || name === "text-underline-offset") return normalized === "auto";
  if (name === "text-transform") return normalized === "none" || normalized === "normal";
  if (name === "lengthAdjust") return normalized === "spacing";
  if (name === "letter-spacing" || name === "word-spacing") return normalized === "normal" || zeroLengthOrPercentage(value);
  if (name === "rotate") return zeroAngle(value);
  if (name === "stroke-dashoffset") return zeroLengthOrPercentage(value);
  if (name === "opacity") return normalized === "1" || normalized === "100%";
  return false;
}

function inspectCoverageTspanRunAttributes(element: Element, style: SvgStyle, tag: string, stats: SvgCoverage, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): void {
  if (tag !== "tspan") return;
  if (!tspanPositionIsSupportedOrNoop(element, style, refs, css, viewport)) {
    for (const attr of ["x", "y", "dx", "dy"]) {
      const value = element.getAttribute(attr);
      if (value != null && !tspanPositionAttrHasNoEffect(attr, value, viewport)) addCoverageCount(stats.unsupported_attributes, attr);
    }
  }
  const declarations = resolvedCascadedDeclarations(element, css, style);
  const textAnchor = declarations["text-anchor"] ?? element.getAttribute("text-anchor");
  if (textAnchor != null && !firstPositionedTspanTextAnchorIsSupported(element, textAnchor) && !tspanTextAnchorHasNoEffect(element, textAnchor)) {
    addCoverageCount(stats.unsupported_attributes, "text-anchor");
  }
}

function tspanPositionIsSupportedOrNoop(element: Element, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  if (!["x", "y", "dx", "dy"].some((attr) => element.hasAttribute(attr))) return true;
  if (!subtreeHasVisibleText(element, style, css, refs, viewport)) return true;
  if (["x", "y", "dx", "dy"].every((attr) => !element.hasAttribute(attr) || tspanPositionAttrHasNoEffect(attr, element.getAttribute(attr) || "", viewport))) return true;
  return firstPositionedTspanPositionIsSupported(element) || lineBreakTspanPositionIsSupported(element);
}

function firstPositionedTspanPositionIsSupported(element: Element): boolean {
  const parent = element.parentElement;
  if (!parent || localName(parent) !== "text") return false;
  if (parent.hasAttribute("x") || parent.hasAttribute("y")) return false;
  if (parent.childNodes[0]?.nodeType === Node.TEXT_NODE && (parent.childNodes[0].textContent || "").trim()) return false;
  if (!element.hasAttribute("x") || !element.hasAttribute("y")) return false;
  return !previousTextTspanHasContent(element);
}

function lineBreakTspanPositionIsSupported(element: Element): boolean {
  return element.hasAttribute("x") && element.hasAttribute("dy") && !element.hasAttribute("y") && !element.hasAttribute("dx");
}

function tspanPositionAttrHasNoEffect(attr: string, value: string, viewport: Viewport): boolean {
  if (attr === "x" || attr === "y") return false;
  const basis = percentageBasis(attr === "dx" ? "x" : "y", viewport);
  const tokens = value.trim().split(/[\s,]+/).filter(Boolean);
  return tokens.length === 0 || tokens.every((token) => parseCssLength(token, basis, Number.NaN) === 0);
}

function firstPositionedTspanTextAnchorIsSupported(element: Element, value: string): boolean {
  if (localName(element) !== "tspan" || normalizeTextAnchor(value) == null) return false;
  return firstPositionedTspanPositionIsSupported(element);
}

function tspanTextAnchorHasNoEffect(element: Element, value: string): boolean {
  if (localName(element) !== "tspan") return false;
  const normalized = value.trim().toLowerCase();
  return ["", "start", "middle", "end"].includes(normalized) && !element.hasAttribute("x") && !element.hasAttribute("y");
}

function firstPositionedTspanBaselineIsSupported(element: Element, name: string, value: string): boolean {
  if (localName(element) !== "tspan" || (name !== "dominant-baseline" && name !== "alignment-baseline")) return false;
  if (normalizeTextBaseline(value) == null) return false;
  if (!firstPositionedTspanPositionIsSupported(element)) return false;
  return true;
}

function previousTextTspanHasContent(element: Element): boolean {
  for (let sibling = element.previousElementSibling; sibling; sibling = sibling.previousElementSibling) {
    if (localName(sibling) === "tspan" && (sibling.textContent || "").trim()) return true;
  }
  return false;
}

function renderingQualityHintHasNoEffect(value: string): boolean {
  return ["auto", "crisp-edges", "crispedges", "geometricprecision", "optimizelegibility", "optimizequality", "optimizespeed", "pixelated"].includes(value);
}

function preserveAspectRatioIsSupportedOrNoop(element: Element, tag: string, value: string, refs: Map<string, Element>): boolean {
  if (tag === "svg" || tag === "symbol") return true;
  if (tag === "use") {
    const href = hrefValue(element);
    const ref = href.startsWith("#") ? refs.get(href.slice(1)) : null;
    return !!ref && (localName(ref) === "svg" || localName(ref) === "symbol");
  }
  if (tag === "image") {
    const [align] = parsePreserveAspectRatio(value);
    return align === "none" || dataImageDimensions(hrefValue(element)) != null;
  }
  return false;
}

function clipRuleHasNoEffect(element: Element): boolean {
  for (let current = element.parentElement; current; current = current.parentElement) {
    if (localName(current) === "clipPath") return false;
  }
  return true;
}

function vectorEffectIsSupportedOrNoop(element: Element, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  return !subtreeHasVisibleStroke(element, style, refs, css, viewport) || normalizeVectorEffect(value) != null;
}

function subtreeHasVisibleStroke(element: Element, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  const tag = localName(element);
  if (style.display === "none") return false;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeHasVisibleStroke(ref, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && coverageStrokeLineEnumApplies(element, tag, style, css, viewport)) return true;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeHasVisibleStroke(selected, computedStyle(selected, style, css, refs, childViewport), refs, css, childViewport, refStack) : false;
  }
  return Array.from(element.children).some((child) => subtreeHasVisibleStroke(child, computedStyle(child, style, css, refs, childViewport), refs, css, childViewport, refStack));
}

function paintOrderHasNoEffect(tag: string, value: string, style: SvgStyle): boolean {
  const normalized = value.trim().toLowerCase().split(/\s+/).join(" ");
  if (["normal", "fill", "fill stroke", "fill stroke markers"].includes(normalized)) return true;
  if (!["circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text", "tspan"].includes(tag)) return false;
  const hasFill = tag !== "line" && style.fill !== "none" && style.fillAlpha !== 0;
  const hasStroke = !!style.stroke && style.stroke !== "none" && style.strokeAlpha !== 0 && (style.strokeWidth ?? 1) > 0;
  if (!(hasFill && hasStroke)) return true;
  if (normalized === "markers fill stroke" || normalized === "fill markers stroke") return !hasVisibleMarker(style);
  return false;
}

function hasVisibleMarker(style: SvgStyle): boolean {
  return !!(style.markerStart || style.markerMid || style.markerEnd);
}

function isolationIsRedundantWithBlend(element: Element, tag: string, value: string, style: SvgStyle, css: CssRule[], refs: Map<string, Element>, viewport: Viewport): boolean {
  return ["g", "svg", "a"].includes(tag) && ["isolate", "auto"].includes(value) && Array.from(element.children).some((child) => subtreeHasBlend(child, style, css, refs, viewport));
}

function subtreeHasBlend(element: Element, inheritedStyle: SvgStyle, css: CssRule[], refs: Map<string, Element>, viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.mixBlendMode && style.mixBlendMode.trim().toLowerCase() !== "normal") return true;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeHasBlend(ref, style, css, refs, refViewport, new Set([...refStack, refId]));
  }
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  return Array.from(element.children).some((child) => subtreeHasBlend(child, style, css, refs, childViewport, refStack));
}

function subtreeHasVisibleFill(element: Element, inheritedStyle: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none") return false;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeHasVisibleFill(ref, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && ["circle", "ellipse", "path", "polygon", "polyline", "rect", "text", "tspan"].includes(tag) && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport) && hasVisibleFill(element, tag, style)) return true;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeHasVisibleFill(selected, style, refs, css, childViewport, refStack) : false;
  }
  return Array.from(element.children).some((child) => subtreeHasVisibleFill(child, style, refs, css, childViewport, refStack));
}

function hasVisibleFill(element: Element, tag: string, style: SvgStyle): boolean {
  if ((tag === "text" || tag === "tspan") && !(element.textContent || "").trim()) return false;
  return tag !== "line" && style.fill !== "none" && style.fillAlpha !== 0;
}

function overflowIsSupportedOrNoop(element: Element, tag: string, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized || normalized === "visible") return true;
  if (tag !== "svg" && tag !== "symbol") return true;
  if (normalizeOverflow(value) !== "hidden") return false;
  return !coverageSubtreeHasVisibleRendering(element, style, refs, css, viewport, new Set());
}

function subtreeHasUnsupportedStrokeLineEnum(element: Element, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, attr: string, refStack: Set<string> = new Set()): boolean {
  const tag = localName(element);
  if (style.display === "none") return false;
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeHasUnsupportedStrokeLineEnum(ref, style, refs, css, refViewport, attr, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && coverageStrokeLineEnumApplies(element, tag, style, css, viewport) && strokeLineEnumIsUnsupported(attr, styleValueForStrokeLineEnum(style, attr))) return true;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeHasUnsupportedStrokeLineEnum(selected, computedStyle(selected, style, css, refs, childViewport), refs, css, childViewport, attr, refStack) : false;
  }
  return Array.from(element.children).some((child) => subtreeHasUnsupportedStrokeLineEnum(child, computedStyle(child, style, css, refs, childViewport), refs, css, childViewport, attr, refStack));
}

function coverageStrokeLineEnumApplies(element: Element, tag: string, style: SvgStyle, css: CssRule[], viewport: Viewport): boolean {
  return ["circle", "ellipse", "line", "path", "polygon", "polyline", "rect", "text", "tspan"].includes(tag) && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport) && !strokeHasNoEffect(tag, style);
}

function strokeLineEnumIsUnsupported(attr: string, value: string | null): boolean {
  if (value == null) return false;
  return attr === "stroke-linecap" ? normalizeStrokeLineCap(value) == null : normalizeStrokeLineJoin(value) == null;
}

function styleValueForStrokeLineEnum(style: SvgStyle, attr: string): string | null {
  return attr === "stroke-linecap" ? style.strokeLineCapSource ?? style.strokeLineCap ?? null : style.strokeLineJoinSource ?? style.strokeLineJoin ?? null;
}

function strokeHasNoEffect(tag: string, style: SvgStyle): boolean {
  return !style.stroke || style.stroke === "none" || style.strokeAlpha === 0 || (style.strokeWidth ?? 1) <= 0 || (tag === "line" && style.stroke === "transparent");
}

function strokeDashoffsetHasNoEffect(value: string, style: SvgStyle, viewport: Viewport): boolean {
  const basis = percentageBasis("diag", viewport);
  const parsed = parseCssLength(value, basis, Number.NaN);
  if (!Number.isFinite(parsed) || numbersClose(parsed, 0)) return Number.isFinite(parsed);
  if (!style.strokeDasharray) return true;
  const period = dashPatternPeriod(style.strokeDasharray, basis);
  if (period == null) return true;
  if (period && numbersClose(Math.abs(parsed) % period, 0)) return true;
  return !style.stroke || style.stroke === "none" || style.strokeAlpha === 0 || (style.strokeWidth ?? 1) <= 0;
}

function strokeDashoffsetIsSupported(value: string, style: SvgStyle, viewport: Viewport): boolean {
  const basis = percentageBasis("diag", viewport);
  const parsed = parseCssLength(value, basis, Number.NaN);
  return Number.isFinite(parsed) && !numbersClose(parsed, 0) && !!style.strokeDasharray && dasharrayWithOffset(style.strokeDasharray, parsed, basis) != null;
}

function dashPatternPeriod(value: string, basis = rootFontSize): number | null {
  const nums = dasharrayNumbers(value, basis);
  if (!nums || nums.reduce((sum, item) => sum + item, 0) <= 0) return null;
  const resolved = nums.length % 2 === 1 ? nums.concat(nums) : nums;
  const period = resolved.reduce((sum, item) => sum + item, 0);
  return period > 0 ? period : null;
}

function pathLengthIsSupportedOrNoop(element: Element, tag: string, value: string, style: SvgStyle, viewport: Viewport, css: CssRule[]): boolean {
  if (normalizePathLength(value) == null) return false;
  const dasharray = style.strokeDasharray;
  if (!dasharray || dasharray.trim().toLowerCase() === "none") return true;
  if (dashPatternPeriod(dasharray, percentageBasis("diag", viewport)) == null) return true;
  if (strokeHasNoEffect(tag, style)) return true;
  if (tag === "line") return pathActualLength(element, tag, viewport, null, css, style) != null;
  if (tag === "polygon" || tag === "polyline") return pathActualLength(element, tag, viewport, parsePoints(element.getAttribute("points") || ""), css, style) != null;
  if (tag === "path") {
    const parsed = parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
    return !!parsed && pathActualLength(element, tag, viewport, parsed.points, css, style) != null;
  }
  return false;
}

function zeroLengthOrPercentage(value: string): boolean {
  const parsed = parseCssLength(value, 100, Number.NaN);
  return Number.isFinite(parsed) && Math.abs(parsed) < 0.000001;
}

function zeroAngle(value: string): boolean {
  const angle = parseAngle(value);
  if (angle == null) return false;
  const remainder = ((angle % 360) + 360) % 360;
  return Math.min(remainder, Math.abs(remainder - 360)) < 0.000001;
}

function textHasNoKerningPairs(element: Element): boolean {
  const tag = localName(element);
  if (tag !== "text" && tag !== "tspan") return false;
  return (element.textContent || "").length <= 1;
}

function inspectCoverageMarkerMid(element: Element, style: SvgStyle, tag: string, stats: SvgCoverage): void {
  if (!style.markerMid || !style.markerMidSource) return;
  if (!style.stroke || style.strokeAlpha === 0 || (style.strokeWidth ?? 1) === 0) return;
  if (!coverageMarkerMidIsUnsupported(element, tag)) return;
  addCoverageCount(stats.unsupported_attributes, style.markerMidSource);
}

function coverageMarkerMidIsUnsupported(element: Element, tag: string): boolean {
  if (tag === "polyline") return parsePoints(element.getAttribute("points") || "").length > 2;
  if (tag === "path") {
    const parsed = parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
    return !!parsed && parsed.points.length > 2;
  }
  return false;
}

function unsupportedPathCommands(value: string): string[] {
  const unsupported = new Set<string>();
  for (const match of value.matchAll(/[A-Za-z]/g)) {
    const command = match[0]!.toUpperCase();
    if (!coverageSupportedPathCommands.has(command)) unsupported.add(command);
  }
  return [...unsupported].sort();
}

function opacityIsSupportedOrNoop(element: Element, tag: string, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  const alpha = parseAlpha(value);
  if (alpha == null || alpha >= 1) return true;
  if (["circle", "ellipse", "image", "line", "path", "polygon", "polyline", "rect", "text", "tspan", "use"].includes(tag)) return true;
  return visibleRenderingDescendantCount(element, style, refs, css, viewport, 2) < 2;
}

function visibleRenderingDescendantCount(element: Element, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, limit: number, refStack: Set<string> = new Set()): number {
  if (limit <= 0 || style.display === "none") return 0;
  const tag = localName(element);
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return 0;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return visibleRenderingDescendantCount(ref, style, refs, css, refViewport, limit, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && ["circle", "ellipse", "image", "line", "path", "polygon", "polyline", "rect", "text", "tspan"].includes(tag) && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport) && !coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport)) return 1;
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? visibleRenderingDescendantCount(selected, computedStyle(selected, style, css, refs, childViewport), refs, css, childViewport, limit, refStack) : 0;
  }
  let total = 0;
  for (const child of Array.from(element.children)) {
    total += visibleRenderingDescendantCount(child, computedStyle(child, style, css, refs, childViewport), refs, css, childViewport, limit - total, refStack);
    if (total >= limit) return total;
  }
  return total;
}

function markerRefIsArrowLike(value: string, refs: Map<string, Element>): boolean {
  if (value.trim().toLowerCase() === "none") return true;
  const ref = urlRef(value);
  if (!ref) return false;
  const marker = refs.get(ref);
  if (!marker || localName(marker) !== "marker") return false;
  return Array.from(marker.children).some((child) => {
    const tag = localName(child);
    if (tag === "path") {
      const parsed = parseBasicPath(child.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
      return !!parsed && parsed.closed && parsed.points.length === 4 && pointsEqual(parsed.points[0]!, parsed.points[3]!);
    }
    if (tag === "polygon" || tag === "polyline") return parsePoints(child.getAttribute("points") || "").length === 3;
    return false;
  });
}

function pointsEqual(a: [number, number], b: [number, number]): boolean {
  return numbersClose(a[0], b[0]) && numbersClose(a[1], b[1]);
}

function normalizeMarkerReference(value: string, refs: Map<string, Element>): boolean {
  if (value.trim().toLowerCase() === "none") return false;
  return markerRefIsArrowLike(value, refs);
}

function markerAttributeIsSupportedOrNoop(element: Element, attr: string, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  if (!markerRefIsArrowLike(value, refs)) return false;
  return subtreeMarkerAttributeIsSupported(element, attr, style, refs, css, viewport);
}

function subtreeMarkerAttributeIsSupported(element: Element, attr: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  if (style.display === "none") return true;
  const tag = localName(element);
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeMarkerAttributeIsSupported(ref, attr, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && coverageStrokeLineEnumApplies(element, tag, style, css, viewport)) return markerTargetIsSupported(element, tag, attr);
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeMarkerAttributeIsSupported(selected, attr, computedStyle(selected, style, css, refs, childViewport), refs, css, childViewport, refStack) : true;
  }
  return Array.from(element.children).every((child) => subtreeMarkerAttributeIsSupported(child, attr, computedStyle(child, style, css, refs, childViewport), refs, css, childViewport, refStack));
}

function markerTargetIsSupported(element: Element, tag: string, attr: string): boolean {
  if (tag === "line") return true;
  if (tag === "polyline") return attr !== "marker" || parsePoints(element.getAttribute("points") || "").length <= 2;
  if (tag === "path") {
    const parsed = parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
    return !!parsed && !parsed.closed && (attr !== "marker" || parsed.points.length <= 2);
  }
  return false;
}

function subtreeMarkerMidHasNoEffect(element: Element, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string> = new Set()): boolean {
  if (style.display === "none") return true;
  const tag = localName(element);
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return false;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeMarkerMidHasNoEffect(ref, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && coverageStrokeLineEnumApplies(element, tag, style, css, viewport)) return !coverageMarkerMidIsUnsupported(element, tag);
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeMarkerMidHasNoEffect(selected, computedStyle(selected, style, css, refs, childViewport), refs, css, childViewport, refStack) : true;
  }
  return Array.from(element.children).every((child) => subtreeMarkerMidHasNoEffect(child, computedStyle(child, style, css, refs, childViewport), refs, css, childViewport, refStack));
}

function clipPathHasRect(value: string, refs: Map<string, Element>): boolean {
  const ref = urlRef(value);
  const clip = ref ? refs.get(ref) : null;
  return !!clip && localName(clip) === "clipPath" && Array.from(clip.children).some((child) => localName(child) === "rect");
}

function clipPathIsSupportedOrNoop(element: Element, tag: string, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  if (clipPathTargetIsSupported(element, tag, value, refs)) return true;
  if (!["a", "g", "svg", "switch", "symbol", "use"].includes(tag)) return false;
  return subtreeClipPathIsSupported(element, value, style, refs, css, viewport, new Set());
}

function clipPathTargetIsSupported(element: Element, tag: string, value: string, refs: Map<string, Element>): boolean {
  if (!clipPathHasRect(value, refs)) return false;
  if (["rect", "circle", "ellipse", "line", "text", "image"].includes(tag)) return true;
  if (tag === "polyline") return parsePoints(element.getAttribute("points") || "").length === 2;
  if (tag === "path") {
    const parsed = parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
    return !!parsed && !parsed.closed && parsed.points.length === 2;
  }
  return false;
}

function subtreeClipPathIsSupported(element: Element, inheritedClipPath: string, inheritedStyle: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport, refStack: Set<string>): boolean {
  const tag = localName(element);
  const style = computedStyle(element, inheritedStyle, css, refs, viewport);
  if (style.display === "none") return true;
  const declarations = resolvedCascadedDeclarations(element, css, style);
  const specifiedClipPath = declarations["clip-path"] ?? element.getAttribute("clip-path");
  if (specifiedClipPath != null && specifiedClipPath !== inheritedClipPath) {
    return !coverageSubtreeHasVisibleRendering(element, style, refs, css, viewport, refStack);
  }
  if (tag === "use") {
    const href = hrefValue(element);
    const refId = href.startsWith("#") ? href.slice(1) : "";
    const ref = refId ? refs.get(refId) : null;
    if (!ref || refStack.has(refId)) return true;
    const refViewport = ["svg", "symbol"].includes(localName(ref)) ? useViewport(ref, element, viewport, css, style) : viewport;
    return subtreeClipPathIsSupported(ref, inheritedClipPath, style, refs, css, refViewport, new Set([...refStack, refId]));
  }
  if (style.visibility !== "hidden" && style.visibility !== "collapse" && ["circle", "ellipse", "image", "line", "path", "polygon", "polyline", "rect", "text"].includes(tag) && !coverageHasNonRenderingGeometry(element, tag, style, css, viewport) && !coverageHasNoVisiblePaint(element, tag, style, refs, css, viewport, refStack)) {
    return clipPathTargetIsSupported(element, tag, inheritedClipPath, refs);
  }
  const childViewport = tag === "svg" ? renderedSvgViewport(element, viewport, css, style) : viewport;
  if (tag === "switch") {
    const selected = switchSelectedChild(element);
    return selected ? subtreeClipPathIsSupported(selected, inheritedClipPath, style, refs, css, childViewport, refStack) : true;
  }
  return Array.from(element.children).every((child) => subtreeClipPathIsSupported(child, inheritedClipPath, style, refs, css, childViewport, refStack));
}

function hasSupportedTextDecorationLine(value: string): boolean {
  return textDecorationLineIsSupportedOrNoop(value);
}

function textDecorationShorthandIsSupported(value: string, style: SvgStyle, viewport: Viewport): boolean {
  const tokens = cssValueTokens(value);
  const lineTokens = new Set(tokens.map((token) => token.toLowerCase()).filter((token) => textDecorationLineTokens.has(token)));
  if (!textDecorationLineTokensAreSupportedOrNoop(lineTokens)) return false;
  if (!lineTokens.size || [...lineTokens].every((token) => token === "none")) return true;
  const styleToken = textDecorationStyleToken(value);
  if (styleToken && styleToken !== "solid" && !hasOnlyVisibleUnderline(style)) return false;
  const colorTokens = tokens.filter((token) => textDecorationColorToken(token) != null);
  if (colorTokens.length > 1) return false;
  if (colorTokens.length === 1 && !textDecorationColorHasNoEffect(colorTokens[0]!, style)) return false;
  const thicknessToken = textDecorationThicknessToken(value);
  if (thicknessToken && !["auto", "from-font"].includes(thicknessToken.trim().toLowerCase()) && !hasOnlyVisibleUnderline(style)) return false;
  if (thicknessToken && !textDecorationThicknessHasNoEffect(thicknessToken, style, viewport)) return false;
  for (const token of tokens) {
    const normalized = token.toLowerCase();
    if (textDecorationLineTokens.has(normalized)) continue;
    if (textDecorationStyleTokens.has(normalized)) continue;
    if (normalized === "auto" || normalized === "from-font") continue;
    if (parseCssColor(token, style)) continue;
    const thickness = parseCssLength(token, percentageBasis("diag", defaultViewport()), Number.NaN);
    if (Number.isFinite(thickness) && thickness >= 0) continue;
    return false;
  }
  return true;
}

function textDecorationLineIsSupportedOrNoop(value: string): boolean {
  const lineTokens = new Set(cssValueTokens(value).map((token) => token.toLowerCase()).filter((token) => textDecorationLineTokens.has(token)));
  return textDecorationLineTokensAreSupportedOrNoop(lineTokens);
}

function textDecorationLineTokensAreSupportedOrNoop(lineTokens: Set<string>): boolean {
  if (!lineTokens.size || [...lineTokens].every((token) => token === "none")) return true;
  return [...lineTokens].every((token) => token === "underline" || token === "line-through");
}

function textDecorationStyleIsSupportedOrNoop(value: string, style: SvgStyle): boolean {
  const normalized = value.trim().toLowerCase();
  if (!hasVisibleTextDecoration(style)) return true;
  if (!normalized || normalized === "solid") return true;
  return textDecorationStyleTokens.has(normalized) && hasOnlyVisibleUnderline(style);
}

function textDecorationColorHasNoEffect(value: string, style: SvgStyle): boolean {
  if (!hasVisibleTextDecoration(style)) return true;
  const color = parseCssColor(value, style);
  if (!color) return false;
  if (hasOnlyVisibleUnderline(style)) return true;
  if (!style.fill || style.fill === "none" || style.fillAlpha != null && style.fillAlpha < 1) return false;
  const alpha = cssColorAlpha(value);
  return color.toLowerCase() === style.fill.toLowerCase() && (alpha == null || alpha >= 1);
}

function textDecorationThicknessHasNoEffect(value: string, style: SvgStyle, viewport: Viewport): boolean {
  const normalized = value.trim().toLowerCase();
  if (!hasVisibleTextDecoration(style) || !normalized || normalized === "auto" || normalized === "from-font") return true;
  return hasOnlyVisibleUnderline(style) && parseCssLength(value, percentageBasis("diag", viewport), Number.NaN) >= 0;
}

function textDecorationStyleToken(value: string | null): string | null {
  if (!value) return null;
  for (const token of cssValueTokens(value)) {
    const normalized = token.toLowerCase();
    if (textDecorationStyleTokens.has(normalized)) return normalized;
  }
  return null;
}

function transformOriginIsSupportedOrNoop(element: Element, value: string, style: SvgStyle, refs: Map<string, Element>, css: CssRule[], viewport: Viewport): boolean {
  const transform = style.transform;
  if (!transform || transform.trim().toLowerCase() === "none") return true;
  if (!coverageSubtreeHasVisibleRendering(element, style, refs, css, viewport, new Set())) return true;
  return transformOriginPoint(element, value, viewport, css, style) != null;
}

function textLengthIsSupported(element: Element, tag: string, value: string, style: SvgStyle, lengthAdjustValue: string | null = style.lengthAdjust ?? null): boolean {
  if (tag !== "text" && tag !== "tspan") return false;
  if (value.includes("%") || style.letterSpacing != null) return false;
  if (lengthAdjustValue != null && normalizeLengthAdjust(lengthAdjustValue) == null) return false;
  const length = parseCssLength(value, style.fontSize ?? rootFontSize, Number.NaN);
  if (!Number.isFinite(length) || length < 0) return false;
  const text = element.textContent || "";
  return !text.includes("\n") && text.trim().length > 1;
}

function wordSpacingHasNoEffect(element: Element, tag: string, value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (normalized === "normal") return true;
  const length = normalizeSpacingLength(value, rootFontSize);
  if (length === 0) return true;
  if (tag === "text" || tag === "tspan") return !/[ \t\f\v]/.test(element.textContent || "");
  return false;
}

function wordSpacingIsSupported(element: Element, tag: string, value: string, style: SvgStyle): boolean {
  if (tag !== "text" && tag !== "tspan") return false;
  if (style.letterSpacing != null || style.textLength != null) return false;
  const spacing = normalizeSpacingLength(value, style.fontSize ?? rootFontSize);
  if (spacing == null) return false;
  const text = element.textContent || "";
  const line = text.trim();
  return !text.includes("\n") && line.length > 1 && wordGapCount(line) > 0;
}

function addCoverageCount(counts: Record<string, number>, key: string): void {
  counts[key] = (counts[key] ?? 0) + 1;
}

function sortedCoverageCounts(counts: Record<string, number>): Record<string, number> {
  return Object.fromEntries(Object.entries(counts).sort(([a], [b]) => a.localeCompare(b)));
}

function declaredSlides(root: Element): Element[] {
  const result: Element[] = [];
  const walk = (element: Element) => {
    if (isSlideElement(element)) {
      result.push(element);
      return;
    }
    for (const child of Array.from(element.children)) {
      if (localName(child) !== "metadata") walk(child);
    }
  };
  walk(root);
  return result;
}

function isSlideElement(element: Element): boolean {
  return element.getAttribute("data-kind") === "slide" || element.getAttribute("data-role") === "slide" || element.hasAttribute("data-slide");
}

function switchSelectedChild(element: Element): Element | null {
  return Array.from(element.children).find(switchChildIsSupported) ?? null;
}

function switchChildIsSupported(element: Element): boolean {
  for (const name of ["requiredExtensions", "requiredFeatures", "requiredFormats"]) {
    if ((element.getAttribute(name) || "").trim()) return false;
  }
  return !(element.getAttribute("systemLanguage") || "").trim();
}

function buildSlideXml(slide: Element, slideIndex: number): string {
  const shapes = extractShapes(slide);
  markRelationConnectors(shapes);
  const body = shapes.map((shape) => shapeToXml(shape)).join("");
  return xmlDecl(`<p:sld xmlns:a="${nsA}" xmlns:r="${nsR}" xmlns:p="${nsP}"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${body}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>`);
}

function buildDrawingMlFragment(slide: Element): string {
  const shapes = extractShapes(slide);
  markRelationConnectors(shapes);
  const body = shapes.map((shape) => shapeToXml(shape)).join("");
  return xmlDecl(`<p:spTree xmlns:a="${nsA}" xmlns:r="${nsR}" xmlns:p="${nsP}"><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>${body}</p:spTree>`);
}

function extractShapes(root: Element): Shape[] {
  const shapes: Shape[] = [];
  const scopeRoot = root.ownerDocument?.documentElement ?? root;
  const css = collectCss(scopeRoot);
  const refs = collectRefs(scopeRoot);
  const viewport = svgViewport(scopeRoot);
  const rootMatrix = localName(scopeRoot) === "svg" ? viewBoxMatrix(scopeRoot, renderedSvgViewport(scopeRoot, viewport, css)) : [1, 0, 0, 1, 0, 0] as Matrix;
  let nextId = 2;
  const walk = (element: Element, matrix: Matrix, inheritedStyle: SvgStyle, refStack: Set<string>, currentViewport: Viewport, activeClip: Box | null = null) => {
    const tag = localName(element);
    if (tag === "metadata" || tag === "defs" || tag === "style") return;
    const ownStyle = computedStyle(element, inheritedStyle, css, refs, currentViewport);
    if (ownStyle.display === "none") return;
    const visibilityHidden = ownStyle.visibility === "hidden" || ownStyle.visibility === "collapse";
    let ownMatrix = multiply(matrix, styleTransformMatrix(element, ownStyle, currentViewport, css));
    let childViewport = currentViewport;
    let childClip = activeClip;
    if (tag === "svg") {
      childViewport = renderedSvgViewport(element, currentViewport, css, ownStyle);
      const declarations = resolvedCascadedDeclarations(element, css, ownStyle);
      const positionedMatrix = multiply(ownMatrix, [1, 0, 0, 1, cascadedGeom(element, declarations, "x", "x", currentViewport), cascadedGeom(element, declarations, "y", "y", currentViewport)]);
      childClip = combineClips(activeClip, svgViewportClip(element, ownStyle, positionedMatrix, childViewport));
      ownMatrix = multiply(positionedMatrix, viewBoxMatrix(element, childViewport));
    }
    const ownContainerClip = rectClipBounds(null, ownStyle, refs, ownMatrix, childViewport, css);
    childClip = combineClips(childClip, ownContainerClip);
    if (tag === "use") {
      const href = hrefValue(element);
      const refId = href.startsWith("#") ? href.slice(1) : "";
      const ref = refs.get(refId);
      if (ref && !refStack.has(refId)) {
        const declarations = resolvedCascadedDeclarations(element, css, ownStyle);
        let useMatrix = multiply(ownMatrix, [1, 0, 0, 1, cascadedGeom(element, declarations, "x", "x", currentViewport), cascadedGeom(element, declarations, "y", "y", currentViewport)]);
        let refViewport = currentViewport;
        if (["svg", "symbol"].includes(localName(ref))) {
          refViewport = useViewport(ref, element, currentViewport, css, ownStyle);
          useMatrix = multiply(useMatrix, viewBoxMatrix(ref, refViewport, element.getAttribute("preserveAspectRatio")));
        }
        walk(ref, useMatrix, ownStyle, new Set([...refStack, refId]), refViewport, childClip);
      }
      return;
    }
    if (tag === "switch") {
      const selected = switchSelectedChild(element);
      if (selected) walk(selected, ownMatrix, ownStyle, refStack, childViewport, childClip);
      return;
    }
    if (!visibilityHidden && tag === "g" && (element.getAttribute("data-kind") === "table" || element.getAttribute("data-role") === "table")) {
      const table = tableFromGroup(element, ownMatrix, nextId, ownStyle, css, childViewport);
      if (table) {
        shapes.push(table);
        nextId += 1;
      }
      return;
    }
    if (!visibilityHidden && tag === "foreignObject") {
      const tableShapes = shapesFromForeignObject(element, ownMatrix, nextId, ownStyle, css, childViewport);
      if (tableShapes.length) {
        shapes.push(...tableShapes);
        nextId += tableShapes.length;
      }
      return;
    }
    const rawShape = tag === "svg" || visibilityHidden ? null : elementToShape(element, ownMatrix, ownStyle, nextId, childViewport, css, refs);
    const clip = combineClips(activeClip, rectClipBounds(rawShape, ownStyle, refs, ownMatrix, childViewport, css));
    const shape = applyClip(rawShape, clip);
    if (shape) {
      shapes.push(shape);
      nextId += 1;
    }
    for (const child of Array.from(element.children)) walk(child, ownMatrix, ownStyle, refStack, childViewport, childClip);
  };
  const baseStyle = scopeRoot === root ? {} : computedStyle(scopeRoot, {}, css, refs, viewport);
  const rootStyle = computedStyle(root, baseStyle, css, refs, viewport);
  for (const child of Array.from(root.children)) walk(child, rootMatrix, rootStyle, new Set(), viewport);
  return extractSvgTables(shapes);
}

function elementToShape(element: Element, matrix: Matrix, style: SvgStyle, id: number, viewport: Viewport, css: CssRule[] = [], refs: Map<string, Element> = new Map()): Shape | null {
  const tag = localName(element);
  const data = dataAttrs(attrs(element));
  const name = element.getAttribute("id") || tag;
  const paintStyle = scaledStrokeStyle(style, strokeTransformScale(style, matrix));
  const declarations = resolvedCascadedDeclarations(element, css, paintStyle);
  if (tag === "rect") {
    const box = transformedBox(matrix, cascadedGeom(element, declarations, "x", "x", viewport), cascadedGeom(element, declarations, "y", "y", viewport), cascadedGeom(element, declarations, "width", "x", viewport), cascadedGeom(element, declarations, "height", "y", viewport));
    return {
      id,
      kind: "rect",
      name,
      data,
      x: box.x,
      y: box.y,
      width: box.width,
      height: box.height,
      rx: rectRadius(element, declarations, viewport),
      fill: paintStyle.fill ?? "#000000",
      fillAlpha: paintStyle.fillAlpha ?? null,
      stroke: paintStyle.stroke ?? null,
      strokeAlpha: paintStyle.strokeAlpha ?? null,
      strokeWidth: paintStyle.strokeWidth ?? 1,
      ...strokeStyle(paintStyle),
    };
  }
  if (tag === "circle" || tag === "ellipse") {
    const cx = cascadedGeom(element, declarations, "cx", "x", viewport);
    const cy = cascadedGeom(element, declarations, "cy", "y", viewport);
    const rx = tag === "circle" ? cascadedGeom(element, declarations, "r", "diag", viewport) : cascadedGeom(element, declarations, "rx", "x", viewport);
    const ry = tag === "circle" ? cascadedGeom(element, declarations, "r", "diag", viewport) : cascadedGeom(element, declarations, "ry", "y", viewport);
    const box = transformedBox(matrix, cx - rx, cy - ry, rx * 2, ry * 2);
    return {
      id,
      kind: "ellipse",
      name,
      data,
      x: box.x,
      y: box.y,
      width: box.width,
      height: box.height,
      fill: paintStyle.fill ?? "#000000",
      fillAlpha: paintStyle.fillAlpha ?? null,
      stroke: paintStyle.stroke ?? null,
      strokeAlpha: paintStyle.strokeAlpha ?? null,
      strokeWidth: paintStyle.strokeWidth ?? 1,
      ...strokeStyle(paintStyle),
    };
  }
  if (tag === "line") {
    const [x1, y1] = point(matrix, cascadedGeom(element, declarations, "x1", "x", viewport), cascadedGeom(element, declarations, "y1", "y", viewport));
    const [x2, y2] = point(matrix, cascadedGeom(element, declarations, "x2", "x", viewport), cascadedGeom(element, declarations, "y2", "y", viewport));
    const pathPaintStyle = scaledPathLengthDashStyle(paintStyle, pathLengthScale(paintStyle, element, "line", viewport, null, css, paintStyle));
    return {
      id,
      kind: "line",
      name,
      data,
      x1,
      y1,
      x2,
      y2,
      stroke: pathPaintStyle.stroke ?? "#111827",
      strokeAlpha: pathPaintStyle.strokeAlpha ?? null,
      strokeWidth: pathPaintStyle.strokeWidth ?? 1,
      ...strokeStyle(pathPaintStyle),
      relation: data.kind === "relation" || data.role === "relation",
      startId: null,
      endId: null,
      markerStart: style.markerStart ?? false,
      markerEnd: style.markerEnd ?? false,
    };
  }
  if (tag === "text") {
    const textMetricScale = matrixScale(matrix);
    const textStyle = scaledTextMetricsStyle(paintStyle, textMetricScale);
    const fontSize = textStyle.fontSize ?? 18;
    const [textX, textY] = svgTextPosition(element, viewport, css, paintStyle);
    const [x, y] = point(matrix, textX, textY);
    const runs = textRuns(element, paintStyle, viewport, textMetricScale, css, refs);
    const text = runs.map((run) => run.text).join("").trim();
    const width = Math.max(80 * textMetricScale, textStyle.textLength ?? text.length * fontSize * 0.62 + wordSpacingExtra(textStyle, text));
    const height = fontSize * 1.35;
    const anchor = textStyle.textAnchor ?? firstPositionedTspanAnchor(element, textStyle, css, refs, viewport);
    const baseline = textStyle.textBaseline ?? firstPositionedTspanBaseline(element, textStyle, css, refs, viewport);
    const rotation = textRotation(element, textStyle, css, refs, viewport);
    return {
      id,
      kind: "text",
      name,
      data,
      x: anchor === "middle" ? x - width / 2 : anchor === "end" ? x - width : x,
      y: baseline === "middle" ? y - height / 2 : baseline === "text-after-edge" ? y - height : y - fontSize,
      width,
      height,
      text,
      fill: textStyle.fill ?? "#111827",
      stroke: textStyle.stroke ?? null,
      strokeAlpha: textStyle.strokeAlpha ?? null,
      strokeWidth: textStyle.strokeWidth ?? 1,
      ...strokeStyle(textStyle),
      fontSize,
      fontFamily: textStyle.fontFamily || "Aptos",
      bold: ["bold", "700", "800", "900"].includes(textStyle.fontWeight || ""),
      italic: isItalic(textStyle),
      fontVariant: textStyle.fontVariant ?? null,
      underline: hasUnderline(textStyle),
      underlineStyle: underlineStyle(textStyle),
      underlineColor: textStyle.textDecorationColor ?? null,
      underlineAlpha: textStyle.textDecorationAlpha ?? null,
      underlineThickness: textStyle.textDecorationThickness ?? null,
      strike: hasStrike(textStyle),
      baselineShift: textStyle.baselineShift ?? null,
      letterSpacing: effectiveLetterSpacing(textStyle, text, fontSize),
      rotation,
      direction: textStyle.direction ?? null,
      anchor,
      baseline,
      runs,
    };
  }
  if (tag === "polygon" || tag === "polyline") {
    const sourcePoints = parsePoints(element.getAttribute("points") || "");
    const points = sourcePoints.map(([x, y]) => point(matrix, x, y));
    if (points.length >= 2) {
      const pathPaintStyle = scaledPathLengthDashStyle(paintStyle, pathLengthScale(paintStyle, element, tag, viewport, sourcePoints));
      return {
        id,
        kind: "freeform",
        name,
        data,
        points,
        closed: tag === "polygon",
        fill: tag === "polygon" ? (pathPaintStyle.fill ?? "#000000") : null,
        fillAlpha: tag === "polygon" ? (pathPaintStyle.fillAlpha ?? null) : null,
        stroke: pathPaintStyle.stroke ?? "#111827",
        strokeAlpha: pathPaintStyle.strokeAlpha ?? null,
        strokeWidth: pathPaintStyle.strokeWidth ?? 1,
        ...strokeStyle(pathPaintStyle),
        markerStart: style.markerStart ?? false,
        markerEnd: style.markerEnd ?? false,
      };
    }
  }
  if (tag === "path") {
    const parsed = parseBasicPath(element.getAttribute("d") || "", matrix);
    if (parsed && parsed.points.length >= 2) {
      const untransformed = parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0]);
      const pathPaintStyle = scaledPathLengthDashStyle(paintStyle, pathLengthScale(paintStyle, element, tag, viewport, untransformed?.points ?? []));
      return {
        id,
        kind: "freeform",
        name,
        data,
        points: parsed.points,
        closed: parsed.closed,
        fill: pathPaintStyle.fill ?? (parsed.closed ? "#000000" : null),
        fillAlpha: pathPaintStyle.fill ? (pathPaintStyle.fillAlpha ?? null) : parsed.closed ? (pathPaintStyle.fillAlpha ?? null) : null,
        stroke: pathPaintStyle.stroke ?? "#111827",
        strokeAlpha: pathPaintStyle.strokeAlpha ?? null,
        strokeWidth: pathPaintStyle.strokeWidth ?? 1,
        ...strokeStyle(pathPaintStyle),
        markerStart: style.markerStart ?? false,
        markerEnd: style.markerEnd ?? false,
      };
    }
  }
  if (tag === "image") {
    const href = hrefValue(element);
    if (supportedDataImage(href)) {
      const imageFit = imagePreserveAspectRatioRect(
        cascadedGeom(element, declarations, "x", "x", viewport),
        cascadedGeom(element, declarations, "y", "y", viewport),
        cascadedGeom(element, declarations, "width", "x", viewport),
        cascadedGeom(element, declarations, "height", "y", viewport),
        href,
        element.getAttribute("preserveAspectRatio"),
      );
      if (imageFit.width <= 0 || imageFit.height <= 0) return null;
      const box = transformedImageBox(matrix, imageFit.x, imageFit.y, imageFit.width, imageFit.height);
      return {
        id,
        kind: "image",
        name,
        data,
        x: box.x,
        y: box.y,
        width: box.width,
        height: box.height,
        href,
        alpha: style.imageAlpha ?? null,
        srcRect: imageFit.srcRect,
        rotation: box.rotation,
        flipH: box.flipH,
        flipV: box.flipV,
      };
    }
  }
  return null;
}

function tableFromGroup(group: Element, matrix: Matrix, id: number, inheritedStyle: SvgStyle, css: CssRule[] = [], viewport: Viewport = defaultViewport()): TableShape | null {
  const rects = semanticTableRects(group);
  if (!rects.length) return null;
  const cells = rects.map(({ rect, source }) => {
    const style = computedStyle(rect, inheritedStyle, css, new Map(), viewport);
    const [x, y] = point(matrix, geom(rect, "x", "x", viewport), geom(rect, "y", "y", viewport));
    return {
      row: Number(source.getAttribute("data-row") || rect.getAttribute("data-row") || 0),
      col: Number(source.getAttribute("data-col") || rect.getAttribute("data-col") || 0),
      colSpan: Math.max(1, Number(source.getAttribute("data-colspan") || source.getAttribute("data-col-span") || rect.getAttribute("data-colspan") || rect.getAttribute("data-col-span") || 1) || 1),
      rowSpan: Math.max(1, Number(source.getAttribute("data-rowspan") || source.getAttribute("data-row-span") || rect.getAttribute("data-rowspan") || rect.getAttribute("data-row-span") || 1) || 1),
      text: source.getAttribute("data-text") || rect.getAttribute("data-text") || source.getAttribute("aria-label") || rect.getAttribute("aria-label") || "",
      x,
      y,
      width: geom(rect, "width", "x", viewport),
      height: geom(rect, "height", "y", viewport),
      fill: style.fill ?? "#ffffff",
      fillAlpha: style.fillAlpha ?? null,
      ...tableCellStyle(style, false),
    };
  });
  const xEdges = edges(cells.flatMap((cell) => [cell.x, cell.x + cell.width]));
  const yEdges = edges(cells.flatMap((cell) => [cell.y, cell.y + cell.height]));
  if (xEdges.length < 2 || yEdges.length < 2) return null;
  const minX = xEdges[0] || 0;
  const minY = yEdges[0] || 0;
  const tableCells = cells.map((cell) => ({
    row: cell.row,
    col: cell.col,
    colSpan: cell.colSpan,
    rowSpan: cell.rowSpan,
    text: cell.text,
    runs: [],
    fill: cell.fill,
    fillAlpha: cell.fillAlpha,
    textFill: cell.textFill,
    textFillAlpha: cell.textFillAlpha,
    textBold: cell.textBold,
    textAlign: cell.textAlign,
    verticalAlign: cell.verticalAlign,
    paddingLeft: cell.paddingLeft,
    paddingRight: cell.paddingRight,
    paddingTop: cell.paddingTop,
    paddingBottom: cell.paddingBottom,
    direction: cell.direction,
    nowrap: cell.nowrap,
    borderLeft: cell.borderLeft,
    borderRight: cell.borderRight,
    borderTop: cell.borderTop,
    borderBottom: cell.borderBottom,
  }));
  return {
    id,
    kind: "table",
    name: group.getAttribute("id") || "table",
    data: dataAttrs(attrs(group)),
    x: minX,
    y: minY,
    columns: xEdges.slice(1).map((edge, index) => edge - (xEdges[index] || 0)),
    rows: yEdges.slice(1).map((edge, index) => edge - (yEdges[index] || 0)),
    cells: tableCells,
  };
}

function semanticTableRects(group: Element): Array<{ rect: Element; source: Element }> {
  const directCells = Array.from(group.querySelectorAll("rect"))
    .filter((rect) => rect.getAttribute("data-kind") === "cell" || rect.getAttribute("data-role") === "cell")
    .map((rect) => ({ rect, source: rect }));
  const groupedCells = Array.from(group.querySelectorAll("g"))
    .filter((cell) => cell.getAttribute("data-kind") === "cell" || cell.getAttribute("data-role") === "cell")
    .flatMap((cell) => Array.from(cell.querySelectorAll("rect")).slice(0, 1).map((rect) => ({ rect, source: cell })));
  const seen = new Set<Element>();
  return [...directCells, ...groupedCells].filter(({ rect }) => {
    if (seen.has(rect)) return false;
    seen.add(rect);
    return true;
  });
}

function extractSvgTables(shapes: Shape[]): Shape[] {
  const extracted = extractSvgRectTable(shapes) ?? extractSvgLineTable(shapes);
  return extracted ?? shapes;
}

function extractSvgRectTable(shapes: Shape[]): Shape[] | null {
  const rects = shapes.filter((shape): shape is RectShape => svgTableRectCandidate(shape));
  if (rects.length < 2 || rects.length !== shapes.filter((shape) => shape.kind === "rect").length) return null;
  const xEdges = tableEdges(rects.flatMap((rect) => [rect.x, rect.x + rect.width]));
  const yEdges = tableEdges(rects.flatMap((rect) => [rect.y, rect.y + rect.height]));
  if (xEdges.length < 2 || yEdges.length < 2) return null;
  const columns = xEdges.slice(1).map((edge, index) => edge - xEdges[index]!);
  const rows = yEdges.slice(1).map((edge, index) => edge - yEdges[index]!);
  if (columns.some((width) => width <= 0) || rows.some((height) => height <= 0)) return null;

  const rowCount = rows.length;
  const columnCount = columns.length;
  const origins = new Map<string, { rect: RectShape; colSpan: number; rowSpan: number }>();
  const occupancy = Array.from({ length: rowCount }, () => Array<string | null>(columnCount).fill(null));
  for (const rect of rects) {
    const col = tableEdgeIndex(xEdges, rect.x);
    const row = tableEdgeIndex(yEdges, rect.y);
    const right = tableEdgeIndex(xEdges, rect.x + rect.width);
    const bottom = tableEdgeIndex(yEdges, rect.y + rect.height);
    if (col == null || row == null || right == null || bottom == null || right <= col || bottom <= row) return null;
    const key = `${row}:${col}`;
    if (origins.has(key)) return null;
    origins.set(key, { rect, colSpan: right - col, rowSpan: bottom - row });
    for (let r = row; r < bottom; r += 1) {
      for (let c = col; c < right; c += 1) {
        if (occupancy[r]?.[c] != null) return null;
        occupancy[r]![c] = key;
      }
    }
  }
  if (occupancy.some((row) => row.some((key) => key == null))) return null;

  const textMap = new Map<string, TextShape>();
  const consumedTextIndexes = new Set<number>();
  shapes.forEach((shape, index) => {
    if (!svgTableTextCandidate(shape)) return;
    const [anchorX, anchorY] = tableTextAnchorPoint(shape);
    const col = tableIntervalIndex(xEdges, anchorX);
    const row = tableIntervalIndex(yEdges, anchorY);
    if (row == null || col == null) return;
    const key = occupancy[row]?.[col];
    if (!key) return;
    if (textMap.has(key)) {
      textMap.set("__duplicate__", shape);
      return;
    }
    textMap.set(key, shape);
    consumedTextIndexes.add(index);
  });
  if (textMap.has("__duplicate__")) return null;

  const gridLines = rectGridLines(shapes, xEdges, yEdges, origins);
  const lineBorders = gridLines ? tableGridBorders(gridLines, xEdges, yEdges) : null;
  const cells: TableCell[] = [];
  for (let row = 0; row < rowCount; row += 1) {
    for (let col = 0; col < columnCount; col += 1) {
      const key = occupancy[row]![col];
      if (key !== `${row}:${col}`) continue;
      const origin = origins.get(key!);
      if (!origin) return null;
      const borders = lineBorders && origin.colSpan === 1 && origin.rowSpan === 1 ? cellGridBorders(lineBorders, row, col) : undefined;
      cells.push(tableCellFromRect(origin.rect, textMap.get(key!), row, col, origin.colSpan, origin.rowSpan, borders));
    }
  }
  const consumedRectIds = new Set(rects.map((rect) => rect.id));
  const consumedLineIds = new Set(gridLines?.map((line) => line.id) ?? []);
  const table: TableShape = {
    id: Math.min(...rects.map((rect) => rect.id)),
    kind: "table",
    name: "svg-grid-table",
    data: {},
    x: xEdges[0]!,
    y: yEdges[0]!,
    columns,
    rows,
    cells,
  };
  const remaining = shapes.filter((shape, index) => !consumedRectIds.has(shape.id) && !consumedLineIds.has(shape.id) && !consumedTextIndexes.has(index));
  return [table, ...remaining];
}

function extractSvgLineTable(shapes: Shape[]): Shape[] | null {
  if (shapes.some((shape) => !["line", "text"].includes(shape.kind))) return null;
  const lines = shapes.filter((shape): shape is LineShape => shape.kind === "line" && svgTableLineCandidate(shape));
  if (lines.length < 4 || lines.length !== shapes.filter((shape) => shape.kind === "line").length) return null;
  const verticals = lines.filter(svgTableVerticalLine);
  const horizontals = lines.filter(svgTableHorizontalLine);
  if (verticals.length < 3 || horizontals.length < 3 || verticals.length + horizontals.length !== lines.length) return null;
  const xEdges = tableEdges(verticals.map(lineMinX));
  const yEdges = tableEdges(horizontals.map(lineMinY));
  if (xEdges.length < 3 || yEdges.length < 3) return null;
  const xMin = xEdges[0]!;
  const xMax = xEdges[xEdges.length - 1]!;
  const yMin = yEdges[0]!;
  const yMax = yEdges[yEdges.length - 1]!;
  if (!tableLinesCoverEdges(verticals, xEdges, yMin, yMax, "vertical")) return null;
  if (!tableLinesCoverEdges(horizontals, yEdges, xMin, xMax, "horizontal")) return null;
  const columns = xEdges.slice(1).map((edge, index) => edge - xEdges[index]!);
  const rows = yEdges.slice(1).map((edge, index) => edge - yEdges[index]!);
  if (columns.some((width) => width <= 0) || rows.some((height) => height <= 0)) return null;
  const borders = tableGridBorders(lines, xEdges, yEdges);
  if (!borders) return null;

  const textMap = new Map<string, TextShape>();
  const consumedTextIndexes = new Set<number>();
  shapes.forEach((shape, index) => {
    if (!svgTableTextCandidate(shape)) return;
    const [anchorX, anchorY] = tableTextAnchorPoint(shape);
    const col = tableIntervalIndex(xEdges, anchorX);
    const row = tableIntervalIndex(yEdges, anchorY);
    if (row == null || col == null) return;
    const key = `${row}:${col}`;
    if (textMap.has(key)) {
      textMap.set("__duplicate__", shape);
      return;
    }
    textMap.set(key, shape);
    consumedTextIndexes.add(index);
  });
  if (textMap.has("__duplicate__")) return null;

  const cells: TableCell[] = [];
  for (let row = 0; row < rows.length; row += 1) {
    for (let col = 0; col < columns.length; col += 1) {
      const rect = syntheticTableRect(xEdges[col]!, yEdges[row]!, columns[col]!, rows[row]!, tableGridPaint(lines));
      cells.push(tableCellFromRect(rect, textMap.get(`${row}:${col}`), row, col, 1, 1, cellGridBorders(borders, row, col)));
    }
  }
  const consumedLineIds = new Set(lines.map((line) => line.id));
  const table: TableShape = {
    id: Math.min(...lines.map((line) => line.id)),
    kind: "table",
    name: "svg-line-grid-table",
    data: {},
    x: xMin,
    y: yMin,
    columns,
    rows,
    cells,
  };
  const remaining = shapes.filter((shape, index) => !consumedLineIds.has(shape.id) && !consumedTextIndexes.has(index));
  return [table, ...remaining];
}

function svgTableRectCandidate(shape: Shape): shape is RectShape {
  return shape.kind === "rect" && shape.width > 0 && shape.height > 0 && numbersClose(shape.rx, 0);
}

function svgTableTextCandidate(shape: Shape): shape is TextShape {
  return shape.kind === "text" && shape.rotation == null;
}

function tableTextAnchorPoint(shape: TextShape): [number, number] {
  const x = shape.anchor === "middle" ? shape.x + shape.width / 2 : shape.anchor === "end" ? shape.x + shape.width : shape.x;
  const y = shape.baseline === "middle" ? shape.y + shape.height / 2 : shape.baseline === "text-after-edge" ? shape.y + shape.height : shape.y + shape.fontSize;
  return [x, y];
}

function tableCellFromRect(rect: RectShape, text: TextShape | undefined, row: number, col: number, colSpan: number, rowSpan: number, borders?: [TableBorder, TableBorder, TableBorder, TableBorder]): TableCell {
  const border = tableBorderFromRect(rect);
  return {
    row,
    col,
    colSpan,
    rowSpan,
    text: text?.text ?? "",
    runs: text?.runs ?? [],
    fill: rect.fill,
    fillAlpha: rect.fillAlpha,
    textFill: text?.fill ?? "#111827",
    textFillAlpha: null,
    textBold: text?.bold ?? false,
    textAlign: text?.anchor ?? null,
    verticalAlign: text?.baseline ?? null,
    paddingLeft: text ? Math.max(0, text.x - rect.x) : 0,
    paddingRight: text ? Math.max(0, rect.x + rect.width - (text.x + text.width)) : 0,
    paddingTop: text ? Math.max(0, text.y - rect.y) : 0,
    paddingBottom: text ? Math.max(0, rect.y + rect.height - (text.y + text.height)) : 0,
    direction: text?.direction ?? null,
    nowrap: false,
    borderLeft: borders?.[0] ?? border,
    borderRight: borders?.[1] ?? border,
    borderTop: borders?.[2] ?? border,
    borderBottom: borders?.[3] ?? border,
  };
}

function tableBorderFromRect(rect: RectShape): TableBorder {
  return {
    stroke: rect.stroke,
    strokeAlpha: rect.strokeAlpha,
    strokeWidth: rect.strokeWidth,
    strokeLineCap: rect.strokeLineCap,
    strokeLineJoin: rect.strokeLineJoin,
    strokeMiterlimit: rect.strokeMiterlimit,
    strokeDasharray: rect.strokeDasharray,
    compound: null,
  };
}

function tableEdges(values: number[]): number[] {
  const result: number[] = [];
  for (const value of values) {
    if (!result.some((edge) => numbersClose(edge, value, 1e-6))) result.push(value);
  }
  return result.sort((a, b) => a - b);
}

function tableEdgeIndex(edges: number[], value: number): number | null {
  const index = edges.findIndex((edge) => numbersClose(edge, value, 1e-6));
  return index >= 0 ? index : null;
}

function tableIntervalIndex(edges: number[], value: number): number | null {
  for (let index = 0; index < edges.length - 1; index += 1) {
    if (value >= edges[index]! - 1e-6 && value <= edges[index + 1]! + 1e-6) return index;
  }
  return null;
}

function rectGridLines(shapes: Shape[], xEdges: number[], yEdges: number[], origins: Map<string, { rect: RectShape; colSpan: number; rowSpan: number }>): LineShape[] | null {
  if (origins.size !== (xEdges.length - 1) * (yEdges.length - 1)) return null;
  if ([...origins.values()].some(({ colSpan, rowSpan }) => colSpan !== 1 || rowSpan !== 1)) return null;
  const lines = shapes.filter((shape): shape is LineShape => shape.kind === "line");
  if (!lines.length || lines.some((line) => !svgTableLineCandidate(line))) return null;
  const verticals = lines.filter(svgTableVerticalLine);
  const horizontals = lines.filter(svgTableHorizontalLine);
  if (verticals.length + horizontals.length !== lines.length) return null;
  if (!tableLinesCoverEdges(verticals, xEdges, yEdges[0]!, yEdges[yEdges.length - 1]!, "vertical")) return null;
  if (!tableLinesCoverEdges(horizontals, yEdges, xEdges[0]!, xEdges[xEdges.length - 1]!, "horizontal")) return null;
  return lines;
}

function svgTableLineCandidate(shape: LineShape): boolean {
  return Boolean(shape.stroke) && (svgTableVerticalLine(shape) || svgTableHorizontalLine(shape));
}

function svgTableVerticalLine(shape: LineShape): boolean {
  return numbersClose(shape.x1, shape.x2, 1e-6) && Math.abs(shape.y2 - shape.y1) > 0;
}

function svgTableHorizontalLine(shape: LineShape): boolean {
  return numbersClose(shape.y1, shape.y2, 1e-6) && Math.abs(shape.x2 - shape.x1) > 0;
}

function tableLinesCoverEdges(lines: LineShape[], edges: number[], start: number, end: number, orientation: "vertical" | "horizontal"): boolean {
  return edges.every((edge) => lines.some((line) => tableLineCoversEdge(line, edge, start, end, orientation)));
}

function tableLineCoversEdge(line: LineShape, edge: number, start: number, end: number, orientation: "vertical" | "horizontal"): boolean {
  if (orientation === "vertical") return numbersClose(lineMinX(line), edge, 1e-6) && numbersClose(lineMinY(line), start, 1e-6) && numbersClose(lineMaxY(line), end, 1e-6);
  return numbersClose(lineMinY(line), edge, 1e-6) && numbersClose(lineMinX(line), start, 1e-6) && numbersClose(lineMaxX(line), end, 1e-6);
}

function tableGridBorders(lines: LineShape[], xEdges: number[], yEdges: number[]): [Map<number, TableBorder>, Map<number, TableBorder>] | null {
  const verticals = new Map<number, TableBorder>();
  const horizontals = new Map<number, TableBorder>();
  for (const line of lines) {
    if (svgTableVerticalLine(line)) {
      const index = tableEdgeIndex(xEdges, lineMinX(line));
      if (index == null) return null;
      verticals.set(index, tableBorderFromLine(line));
    } else if (svgTableHorizontalLine(line)) {
      const index = tableEdgeIndex(yEdges, lineMinY(line));
      if (index == null) return null;
      horizontals.set(index, tableBorderFromLine(line));
    } else {
      return null;
    }
  }
  for (let index = 0; index < xEdges.length; index += 1) if (!verticals.has(index)) return null;
  for (let index = 0; index < yEdges.length; index += 1) if (!horizontals.has(index)) return null;
  return [verticals, horizontals];
}

function cellGridBorders(borders: [Map<number, TableBorder>, Map<number, TableBorder>], row: number, col: number): [TableBorder, TableBorder, TableBorder, TableBorder] {
  const [verticals, horizontals] = borders;
  return [verticals.get(col)!, verticals.get(col + 1)!, horizontals.get(row)!, horizontals.get(row + 1)!];
}

function tableBorderFromLine(line: LineShape): TableBorder {
  return {
    stroke: line.stroke,
    strokeAlpha: line.strokeAlpha,
    strokeWidth: line.strokeWidth,
    strokeLineCap: line.strokeLineCap,
    strokeLineJoin: line.strokeLineJoin,
    strokeMiterlimit: line.strokeMiterlimit,
    strokeDasharray: line.strokeDasharray,
    compound: null,
  };
}

function tableGridPaint(lines: LineShape[]): TableBorder {
  return tableBorderFromLine(lines.find((line) => line.stroke) ?? lines[0]!);
}

function syntheticTableRect(x: number, y: number, width: number, height: number, border: TableBorder): RectShape {
  return {
    id: 0,
    kind: "rect",
    name: "table-cell",
    data: {},
    x,
    y,
    width,
    height,
    rx: 0,
    fill: null,
    fillAlpha: null,
    stroke: border.stroke,
    strokeAlpha: border.strokeAlpha,
    strokeWidth: border.strokeWidth,
    strokeLineCap: border.strokeLineCap,
    strokeLineJoin: border.strokeLineJoin,
    strokeMiterlimit: border.strokeMiterlimit,
    strokeDasharray: border.strokeDasharray,
    strokeDashoffset: null,
  };
}

function lineMinX(line: LineShape): number { return Math.min(line.x1, line.x2); }
function lineMaxX(line: LineShape): number { return Math.max(line.x1, line.x2); }
function lineMinY(line: LineShape): number { return Math.min(line.y1, line.y2); }
function lineMaxY(line: LineShape): number { return Math.max(line.y1, line.y2); }

function shapesFromForeignObject(element: Element, matrix: Matrix, id: number, inheritedStyle: SvgStyle, css: CssRule[] = [], viewport: Viewport = defaultViewport()): Shape[] {
  const table = Array.from(element.querySelectorAll("table")).find((item) => localName(item) === "table");
  if (!table) return [];
  if (!matrixKeepsRectUpright(matrix)) return [];
  const grid = htmlTableGrid(table);
  if (!grid) return [];
  const { rows, columnCount } = grid;
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
  const box = transformedBox(matrix, cascadedGeom(element, declarations, "x", "x", viewport), cascadedGeom(element, declarations, "y", "y", viewport), cascadedGeom(element, declarations, "width", "x", viewport), cascadedGeom(element, declarations, "height", "y", viewport));
  if (box.width <= 0 || box.height <= 0) return [];
  const tableStyle = htmlElementStyle(table, inheritedStyle, css);
  const tableWidth = htmlTableElementSize(table, "width", box.width) ?? box.width;
  const tableHeight = htmlTableElementSize(table, "height", box.height) ?? box.height;
  const tableX = htmlTableXOffset(table, box.width, tableWidth, css);
  const tableYOffset = htmlTableYOffset(table);
  const frameX = box.x + tableX;
  const frameY = box.y + tableYOffset;
  const caption = htmlTableCaption(table);
  const captionStyle = caption ? htmlElementStyle(caption, tableStyle, css) : null;
  const captionText = caption ? htmlCellText(caption) : "";
  const captionHeight = htmlCaptionHeight(captionText, captionStyle, tableHeight);
  const captionBottom = htmlCaptionSide(caption, css) === "bottom";
  const tableId = captionText && !captionBottom ? id + 1 : id;
  const captionId = captionText && !captionBottom ? id : id + 1;
  const tableY = frameY + (captionText && !captionBottom ? captionHeight : 0);
  const gridHeight = Math.max(1, tableHeight - captionHeight);
  const spacing = htmlTableHasSpans(rows) ? [0, 0] as [number, number] : htmlTableBorderSpacing(table, css, tableWidth, gridHeight);
  const spaced = spacing[0] > 0 || spacing[1] > 0;
  const dataWidth = spaced ? Math.max(1, tableWidth - spacing[0] * (columnCount + 1)) : tableWidth;
  const dataHeight = spaced ? Math.max(1, gridHeight - spacing[1] * (rows.length + 1)) : gridHeight;
  const dataColumns = htmlTableColumns(table, columnCount, dataWidth);
  const dataRows = htmlTableRowHeights(rows, dataHeight);
  const columnBackgrounds = htmlTableColumnBackgrounds(table, columnCount, css);
  const columns = spaced ? interleaveSpacers(dataColumns, spacing[0]) : dataColumns;
  const rowHeights = spaced ? interleaveSpacers(dataRows, spacing[1]) : dataRows;
  const occupied = Array.from({ length: rows.length }, () => Array<boolean>(columnCount).fill(false));
  const cells: TableCell[] = [];
  rows.forEach((row, rowIndex) => {
    let column = 0;
    for (const cellElement of htmlRowCells(row)) {
      while (column < columnCount && occupied[rowIndex]?.[column]) column += 1;
      if (column >= columnCount) break;
      const colSpan = Math.min(Math.max(1, htmlSpan(cellElement, "colspan")), columnCount - column);
      const rowSpan = Math.min(Math.max(1, htmlSpan(cellElement, "rowspan")), rows.length - rowIndex);
      for (let r = rowIndex; r < rowIndex + rowSpan; r += 1) {
        for (let c = column; c < column + colSpan; c += 1) {
          if (occupied[r]) occupied[r]![c] = true;
        }
      }
      const style = htmlTableCellStyle(cellElement, table, inheritedStyle, css);
      const runs = htmlTextRuns(cellElement, style, css);
      const fill = htmlTableCellFill(cellElement, table, columnBackgrounds[column] ?? [], css) ?? { color: style.fill ?? "#ffffff", alpha: style.fillAlpha ?? null };
      cells.push({
        row: spaced ? rowIndex * 2 + 1 : rowIndex,
        col: spaced ? column * 2 + 1 : column,
        colSpan,
        rowSpan,
        text: runs.length ? runs.map((run) => run.text).join("") : htmlCellText(cellElement),
        runs,
        fill: fill.color,
        fillAlpha: fill.alpha,
        ...tableCellStyle(style, localName(cellElement) === "th"),
      });
      column += colSpan;
    }
  });
  if (!cells.length) return [];
  if (spaced) cells.push(...htmlTableSpacerCells(columns.length, rowHeights.length, cells, tableStyle));
  const tableShape: TableShape = {
    id: tableId,
    kind: "table",
    name: element.getAttribute("id") || table.getAttribute("id") || "foreignObject-table",
    data: dataAttrs(attrs(element)),
    x: frameX,
    y: tableY,
    columns,
    rows: rowHeights,
    cells,
  };
  if (!caption || !captionText || !captionStyle || captionHeight <= 0) return [tableShape];
  const captionShape = htmlCaptionShape(caption, captionStyle, captionId, frameX, captionBottom ? frameY + gridHeight : frameY, tableWidth, captionHeight, css);
  return captionBottom ? [tableShape, captionShape] : [captionShape, tableShape];
}

function tableCellStyle(style: SvgStyle, header: boolean): Omit<TableCell, "row" | "col" | "colSpan" | "rowSpan" | "text" | "runs" | "fill" | "fillAlpha"> {
  const border = tableBorderFromStyle(style);
  return {
    textFill: style.color ?? style.fill ?? "#111827",
    textFillAlpha: style.color ? (style.colorAlpha ?? null) : (style.fillAlpha ?? null),
    textBold: header || ["bold", "700", "800", "900"].includes(style.fontWeight || ""),
    textAlign: style.tableCellTextAlign ?? (header ? "center" : null),
    verticalAlign: style.tableCellVerticalAlign ?? "middle",
    paddingLeft: style.tableCellPaddingLeft ?? style.tableCellPadding ?? 0,
    paddingRight: style.tableCellPaddingRight ?? style.tableCellPadding ?? 0,
    paddingTop: style.tableCellPaddingTop ?? style.tableCellPadding ?? 0,
    paddingBottom: style.tableCellPaddingBottom ?? style.tableCellPadding ?? 0,
    direction: style.direction ?? null,
    nowrap: style.tableCellNowrap ?? false,
    borderLeft: style.tableBorderLeft ?? border,
    borderRight: style.tableBorderRight ?? border,
    borderTop: style.tableBorderTop ?? border,
    borderBottom: style.tableBorderBottom ?? border,
  };
}

function tableBorderFromStyle(style: SvgStyle): TableBorder {
  return {
    stroke: style.stroke ?? null,
    strokeAlpha: style.strokeAlpha ?? null,
    strokeWidth: style.strokeWidth ?? 1,
    ...strokeStyle(style),
    compound: style.tableBorderCompound ?? null,
  };
}

function htmlTableRows(table: Element): Element[] {
  return Array.from(table.querySelectorAll("tr")).filter((item) => localName(item) === "tr");
}

function htmlTableGrid(table: Element): { rows: Element[]; columnCount: number } | null {
  const rows = htmlTableRows(table).filter((row) => htmlRowCells(row).length > 0);
  if (!rows.length) return null;
  const occupied: boolean[][] = [];
  const placements: Array<{ row: number; rowSpan: number }> = [];
  let columnCount = 0;
  rows.forEach((row, rowIndex) => {
    occupied[rowIndex] ||= [];
    let column = 0;
    for (const cell of htmlRowCells(row)) {
      while (occupied[rowIndex]?.[column]) column += 1;
      const colSpan = Math.max(1, htmlSpan(cell, "colspan"));
      const rowSpan = Math.max(1, htmlSpan(cell, "rowspan"));
      placements.push({ row: rowIndex, rowSpan });
      for (let r = rowIndex; r < rowIndex + rowSpan; r += 1) {
        occupied[r] ||= [];
        for (let c = column; c < column + colSpan; c += 1) occupied[r]![c] = true;
      }
      column += colSpan;
      columnCount = Math.max(columnCount, column);
    }
  });
  if (placements.some((item) => item.row + item.rowSpan > rows.length)) return null;
  for (let rowIndex = 0; rowIndex < rows.length; rowIndex += 1) {
    let filled = 0;
    for (let column = 0; column < columnCount; column += 1) {
      if (occupied[rowIndex]?.[column]) filled += 1;
    }
    if (filled !== columnCount) return null;
  }
  return columnCount > 0 ? { rows, columnCount } : null;
}

function htmlRowCells(row: Element): Element[] {
  return Array.from(row.children).filter((item) => ["td", "th"].includes(localName(item)));
}

function htmlTableHasSpans(rows: Element[]): boolean {
  return rows.some((row) => htmlRowCells(row).some((cell) => htmlSpan(cell, "colspan") > 1 || htmlSpan(cell, "rowspan") > 1));
}

function htmlTableBorderSpacing(table: Element, css: CssRule[], width: number, height: number): [number, number] {
  const collapse = htmlCssValue(table, "border-collapse", css);
  if (collapse?.trim().toLowerCase() === "collapse") return [0, 0];
  const value = htmlCssValue(table, "border-spacing", css) ?? table.getAttribute("cellspacing");
  if (!value) return [0, 0];
  const parts = cssValueTokens(value);
  if (!parts.length) return [0, 0];
  const x = htmlTableFitSpacing(htmlCssLength(parts[0] ?? null, width) ?? 0, width);
  const y = htmlTableFitSpacing(htmlCssLength(parts[1] ?? parts[0] ?? null, height) ?? x, height);
  return [x, y];
}

function htmlTableFitSpacing(spacing: number, size: number): number {
  if (spacing <= 0 || size <= 0) return 0;
  return Math.min(spacing, size / 3);
}

function interleaveSpacers(values: number[], spacing: number): number[] {
  const result: number[] = [spacing];
  for (const value of values) result.push(value, spacing);
  return result;
}

function htmlTableSpacerCells(columnCount: number, rowCount: number, dataCells: TableCell[], tableStyle: SvgStyle): TableCell[] {
  const dataPositions = new Set(dataCells.map((cell) => `${cell.row}:${cell.col}`));
  const fill = tableStyle.fill ?? "#ffffff";
  const spacerStyle: SvgStyle = { fill, stroke: null, strokeWidth: 0 };
  const cells: TableCell[] = [];
  for (let row = 0; row < rowCount; row += 1) {
    for (let col = 0; col < columnCount; col += 1) {
      if (dataPositions.has(`${row}:${col}`)) continue;
      cells.push({
        row,
        col,
        colSpan: 1,
        rowSpan: 1,
        text: "",
        runs: [],
        fill,
        fillAlpha: tableStyle.fillAlpha ?? null,
        ...tableCellStyle(spacerStyle, false),
      });
    }
  }
  return cells;
}

function htmlTableCaption(table: Element): Element | null {
  return Array.from(table.children).find((item) => localName(item) === "caption") ?? null;
}

function htmlCaptionSide(caption: Element | null, css: CssRule[]): "top" | "bottom" {
  if (!caption) return "top";
  const value = htmlCssValue(caption, "caption-side", css);
  return value?.trim().toLowerCase() === "bottom" ? "bottom" : "top";
}

function htmlCaptionHeight(text: string, style: SvgStyle | null, tableHeight: number): number {
  if (!text || tableHeight <= 0) return 0;
  const fontSize = style?.fontSize ?? 14;
  return Math.min(Math.max(1, fontSize * 1.4), tableHeight / 3);
}

function htmlCaptionShape(caption: Element, style: SvgStyle, id: number, x: number, y: number, width: number, height: number, css: CssRule[]): TextShape {
  const runs = htmlTextRuns(caption, style, css);
  const text = runs.map((run) => run.text).join("");
  return {
    id,
    kind: "text",
    name: caption.getAttribute("id") || "caption",
    data: dataAttrs(attrs(caption)),
    x,
    y,
    width,
    height,
    text,
    fill: style.color ?? "#000000",
    stroke: style.stroke ?? null,
    strokeAlpha: style.strokeAlpha ?? null,
    strokeWidth: style.strokeWidth ?? 1,
    ...strokeStyle(style),
    fontSize: style.fontSize ?? 14,
    fontFamily: style.fontFamily || "Aptos",
    bold: ["bold", "700", "800", "900"].includes(style.fontWeight || ""),
    italic: isItalic(style),
    fontVariant: style.fontVariant ?? null,
    underline: hasUnderline(style),
    underlineStyle: underlineStyle(style),
    underlineColor: style.textDecorationColor ?? null,
    underlineAlpha: style.textDecorationAlpha ?? null,
    underlineThickness: style.textDecorationThickness ?? null,
    strike: hasStrike(style),
    baselineShift: style.baselineShift ?? null,
    letterSpacing: style.letterSpacing ?? null,
    rotation: null,
    direction: style.direction ?? null,
    anchor: "middle",
    baseline: "middle",
    runs,
  };
}

function htmlSpan(element: Element, name: string): number {
  const raw = element.getAttribute(name);
  const value = raw == null ? 1 : dmlInt(raw, 1);
  return Number.isFinite(value) && value > 0 ? value : 1;
}

function htmlTableColumns(table: Element, count: number, width: number): number[] {
  const specs: Array<number | null> = [];
  for (const child of Array.from(table.children)) {
    const tag = localName(child);
    const cols = tag === "colgroup"
      ? Array.from(child.children).filter((item) => localName(item) === "col")
      : tag === "col" ? [child] : [];
    for (const col of cols) {
      const columnWidth = htmlCssLength(htmlStyleValue(col, "width") ?? col.getAttribute("width"), width);
      const span = Math.max(1, htmlSpan(col, "span"));
      for (let index = 0; index < span; index += 1) specs.push(columnWidth);
      if (specs.length >= count) break;
    }
    if (specs.length >= count) break;
  }
  return htmlTableSizes(specs.length ? specs : htmlTableFirstRowColumnWidths(table, count, width), count, width);
}

function htmlTableFirstRowColumnWidths(table: Element, count: number, width: number): Array<number | null> {
  const specs: Array<number | null> = [];
  for (const row of Array.from(table.querySelectorAll("tr")).filter((item) => localName(item) === "tr")) {
    for (const cell of htmlRowCells(row)) {
      const cellWidth = htmlCssLength(htmlStyleValue(cell, "width") ?? cell.getAttribute("width"), width);
      const colSpan = Math.max(1, htmlSpan(cell, "colspan"));
      const columnWidth = cellWidth != null ? cellWidth / colSpan : null;
      for (let index = 0; index < colSpan; index += 1) specs.push(columnWidth);
      if (specs.length >= count) return specs;
    }
    if (specs.length) return specs;
  }
  return specs;
}

function htmlTableSizes(specs: Array<number | null>, count: number, size: number): number[] {
  if (count <= 0) return [];
  const normalized = specs.slice(0, count);
  while (normalized.length < count) normalized.push(null);
  const fixedTotal = normalized.reduce<number>((sum, item) => sum + (item ?? 0), 0);
  const missing = normalized.filter((item) => item == null).length;
  if (fixedTotal <= 0) return Array.from({ length: count }, () => Math.max(1, size / count));
  if (missing) {
    const fallback = fixedTotal < size ? (size - fixedTotal) / missing : size / count;
    const sized = normalized.map((item) => item != null && item > 0 ? item : fallback);
    const sizedTotal = sized.reduce((sum, item) => sum + item, 0);
    const scale = sizedTotal > 0 ? size / sizedTotal : 1;
    return sized.map((item) => Math.max(1, item * scale));
  }
  const scale = fixedTotal > 0 ? size / fixedTotal : 1;
  return normalized.map((item) => Math.max(1, (item ?? 0) * scale));
}

function htmlTableElementSize(table: Element, axis: "width" | "height", basis: number): number | null {
  const value = htmlStyleValue(table, axis) ?? table.getAttribute(axis);
  const parsed = htmlCssLength(value, basis);
  return parsed != null && parsed > 0 ? parsed : null;
}

function htmlTableXOffset(table: Element, containerWidth: number, tableWidth: number, css: CssRule[]): number {
  const extra = Math.max(0, containerWidth - tableWidth);
  const marginLeft = htmlMarginSide(table, "left");
  const marginRight = htmlMarginSide(table, "right");
  if (marginLeft === "auto" && marginRight === "auto") return extra / 2;
  if (marginLeft === "auto") return extra;
  if (typeof marginLeft === "number") return marginLeft;
  const align = (htmlCssValue(table, "text-align", css) ?? table.getAttribute("align") ?? "").trim().toLowerCase();
  if (align === "center" || align === "middle") return extra / 2;
  if (align === "right" || align === "end") return extra;
  return 0;
}

function htmlTableYOffset(table: Element): number {
  const marginTop = htmlMarginSide(table, "top");
  return typeof marginTop === "number" ? marginTop : 0;
}

function htmlMarginSide(element: Element, side: "top" | "right" | "bottom" | "left"): number | "auto" | null {
  const value = htmlStyleValue(element, `margin-${side}`) ?? htmlMarginShorthandSide(htmlStyleValue(element, "margin"), side);
  if (value == null) return null;
  const normalized = value.trim().toLowerCase();
  if (normalized === "auto") return "auto";
  const parsed = htmlCssLength(normalized, 0);
  return parsed != null ? Math.max(0, parsed) : null;
}

function htmlMarginShorthandSide(value: string | null, side: "top" | "right" | "bottom" | "left"): string | null {
  if (!value) return null;
  const parts = cssValueTokens(value).slice(0, 4);
  if (!parts.length) return null;
  const [top, right, bottom, left] = parts.length === 1
    ? [parts[0], parts[0], parts[0], parts[0]]
    : parts.length === 2
      ? [parts[0], parts[1], parts[0], parts[1]]
      : parts.length === 3
        ? [parts[0], parts[1], parts[2], parts[1]]
        : [parts[0], parts[1], parts[2], parts[3]];
  return { top, right, bottom, left }[side] ?? null;
}

function htmlTableColumnBackgrounds(table: Element, count: number, css: CssRule[]): HtmlFill[][] {
  const backgrounds: HtmlFill[][] = [];
  for (const child of Array.from(table.children)) {
    const tag = localName(child);
    const colgroupFill = tag === "colgroup" ? htmlElementBackgroundFill(child, css) : null;
    const cols = tag === "colgroup"
      ? Array.from(child.children).filter((item) => localName(item) === "col")
      : tag === "col" ? [child] : [];
    for (const col of cols) {
      const layers = [htmlElementBackgroundFill(col, css), colgroupFill].filter((item): item is HtmlFill => item != null);
      const span = Math.max(1, htmlSpan(col, "span"));
      for (let index = 0; index < span; index += 1) backgrounds.push(layers);
      if (backgrounds.length >= count) break;
    }
    if (backgrounds.length >= count) break;
  }
  while (backgrounds.length < count) backgrounds.push([]);
  return backgrounds.slice(0, count);
}

function htmlTableCellFill(cell: Element, table: Element, columnBackgrounds: HtmlFill[], css: CssRule[]): HtmlFill | null {
  const ancestors = htmlAncestorsBetween(table, cell);
  const row = findLastElement(ancestors, (item) => localName(item) === "tr");
  const rowGroup = findLastElement(ancestors, (item) => ["thead", "tbody", "tfoot"].includes(localName(item)));
  const candidates = [
    htmlElementBackgroundFill(cell, css),
    row ? htmlElementBackgroundFill(row, css) : null,
    rowGroup ? htmlElementBackgroundFill(rowGroup, css) : null,
    ...columnBackgrounds,
    htmlElementBackgroundFill(table, css),
  ];
  return candidates.find((item): item is HtmlFill => item != null) ?? null;
}

function findLastElement(items: Element[], predicate: (item: Element) => boolean): Element | null {
  for (let index = items.length - 1; index >= 0; index -= 1) {
    const item = items[index]!;
    if (predicate(item)) return item;
  }
  return null;
}

function htmlAncestorsBetween(root: Element, element: Element): Element[] {
  const ancestors: Element[] = [];
  let current = element.parentElement;
  while (current && current !== root) {
    ancestors.push(current);
    current = current.parentElement;
  }
  return ancestors;
}

function htmlElementBackgroundFill(element: Element, css: CssRule[]): HtmlFill | null {
  const declarations = resolvedCascadedDeclarations(element, css, {}, htmlAttributeAliases(element));
  const background = declarations["background-color"] ?? declarations["background"] ?? element.getAttribute("bgcolor");
  const fill = htmlFirstColorFill(background, {});
  return fill?.color == null ? null : fill;
}

function htmlTableRowHeights(rows: Element[], height: number): number[] {
  const explicit = rows.map((row) => htmlCssLength(htmlStyleValue(row, "height") ?? row.getAttribute("height"), height));
  return htmlTableSizes(explicit, rows.length, height);
}

function htmlTableCellStyle(cell: Element, table: Element, inheritedStyle: SvgStyle, css: CssRule[]): SvgStyle {
  const tableStyle = htmlElementStyle(table, inheritedStyle, css);
  const rowStyle = cell.parentElement ? htmlElementStyle(cell.parentElement, tableStyle, css) : tableStyle;
  return htmlElementStyle(cell, rowStyle, css);
}

function htmlElementStyle(element: Element, inheritedStyle: SvgStyle, css: CssRule[]): SvgStyle {
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle, htmlAttributeAliases(element));
  const value = (name: string): string | null => declarations[name] ?? null;
  const next: SvgStyle = { ...inheritedStyle, customProperties: customPropertiesFromDeclarations(declarations, inheritedStyle) };
  const color = value("color");
  const background = value("background-color") ?? value("background") ?? element.getAttribute("bgcolor");
  const border = value("border") ?? (element.hasAttribute("border") ? `${element.getAttribute("border") || "1"} solid` : null);
  const borderColor = value("border-color") ?? element.getAttribute("bordercolor");
  const borderWidth = value("border-width") ?? element.getAttribute("border");
  const borderStyle = value("border-style");
  const padding = value("padding") ?? element.getAttribute("cellpadding");
  const paddingLeft = value("padding-left");
  const paddingRight = value("padding-right");
  const paddingTop = value("padding-top");
  const paddingBottom = value("padding-bottom");
  const textAlign = value("text-align") ?? element.getAttribute("align");
  const verticalAlign = value("vertical-align") ?? element.getAttribute("valign");
  const whiteSpace = value("white-space");
  const fontSize = value("font-size");
  const fontFamily = value("font-family") ?? element.getAttribute("face");
  const fontWeight = value("font-weight");
  const fontStyle = value("font-style");
  const fontVariant = value("font-variant");
  const textTransform = value("text-transform");
  const textDecoration = [value("text-decoration-line") ?? value("text-decoration"), value("text-decoration-style")].filter(Boolean).join(" ") || null;
  const textDecorationColor = value("text-decoration-color");
  const textDecorationThickness = value("text-decoration-thickness");
  const direction = value("direction");
  const letterSpacing = value("letter-spacing");
  if (color != null) {
    next.color = parseCssColor(color, next) ?? next.color ?? null;
    next.colorAlpha = cssColorAlpha(color);
  }
  if (background != null) {
    const fill = htmlFirstColorFill(background, next);
    next.fill = fill?.color ?? null;
    next.fillAlpha = fill?.alpha ?? null;
  }
  const parsedBorder = parseHtmlBorder(border, next);
  if (border != null) {
    next.stroke = parsedBorder.stroke;
    next.strokeAlpha = parsedBorder.strokeAlpha;
    next.strokeWidth = parsedBorder.strokeWidth;
    next.strokeDasharray = parsedBorder.strokeDasharray;
    next.tableBorderCompound = parsedBorder.compound;
  }
  if (borderColor != null) {
    next.stroke = parseCssColor(borderColor, next);
    next.strokeAlpha = cssColorAlpha(borderColor);
  }
  if (borderWidth != null) next.strokeWidth = htmlCssLength(borderWidth, 1) ?? next.strokeWidth ?? 1;
  if (borderStyle != null) applyHtmlBorderStyle(next, borderStyle);
  if (padding != null) {
    const sides = htmlPaddingSides(padding);
    if (sides) {
      next.tableCellPaddingTop = sides.top;
      next.tableCellPaddingRight = sides.right;
      next.tableCellPaddingBottom = sides.bottom;
      next.tableCellPaddingLeft = sides.left;
      next.tableCellPadding = sides.top;
    } else {
      next.tableCellPadding = htmlCssLength(padding, 0) ?? next.tableCellPadding ?? 0;
    }
  }
  if (paddingLeft != null) next.tableCellPaddingLeft = htmlCssLength(paddingLeft, 0) ?? next.tableCellPaddingLeft ?? next.tableCellPadding ?? 0;
  if (paddingRight != null) next.tableCellPaddingRight = htmlCssLength(paddingRight, 0) ?? next.tableCellPaddingRight ?? next.tableCellPadding ?? 0;
  if (paddingTop != null) next.tableCellPaddingTop = htmlCssLength(paddingTop, 0) ?? next.tableCellPaddingTop ?? next.tableCellPadding ?? 0;
  if (paddingBottom != null) next.tableCellPaddingBottom = htmlCssLength(paddingBottom, 0) ?? next.tableCellPaddingBottom ?? next.tableCellPadding ?? 0;
  if (textAlign != null) next.tableCellTextAlign = normalizeHtmlTextAlign(textAlign);
  if (verticalAlign != null) next.tableCellVerticalAlign = normalizeHtmlVerticalAlign(verticalAlign);
  if (whiteSpace != null) next.tableCellNowrap = htmlWhiteSpaceWrap(whiteSpace) === "none";
  if (element.hasAttribute("nowrap")) next.tableCellNowrap = true;
  const currentBorder = tableBorderFromStyle(next);
  next.tableBorderLeft = htmlSideBorder(declarations, "left", currentBorder, next);
  next.tableBorderRight = htmlSideBorder(declarations, "right", currentBorder, next);
  next.tableBorderTop = htmlSideBorder(declarations, "top", currentBorder, next);
  next.tableBorderBottom = htmlSideBorder(declarations, "bottom", currentBorder, next);
  const tag = localName(element);
  const fontTagSize = tag === "font" ? htmlFontSize(element.getAttribute("size")) : null;
  const fontTagColor = tag === "font" ? element.getAttribute("color") : null;
  if (fontTagColor != null) {
    next.color = parseCssColor(fontTagColor, next) ?? next.color ?? null;
    next.colorAlpha = cssColorAlpha(fontTagColor);
  }
  if (fontSize != null) next.fontSize = parseFontSize(fontSize, next.fontSize ?? 14);
  if (fontTagSize != null) next.fontSize = fontTagSize;
  if (fontFamily != null) next.fontFamily = normalizeFontFamily(fontFamily);
  if (fontWeight != null) next.fontWeight = fontWeight;
  if (["strong", "b"].includes(tag) && htmlFontWeightIsNormal(next.fontWeight)) next.fontWeight = "bold";
  if (fontStyle != null) next.fontStyle = fontStyle;
  if (["em", "i"].includes(tag) && htmlFontStyleIsNormal(next.fontStyle)) next.fontStyle = "italic";
  if (fontVariant != null) next.fontVariant = normalizeFontVariant(fontVariant);
  if (textTransform != null) next.textTransform = normalizeTextTransform(textTransform);
  if (textDecoration != null) next.textDecoration = textDecoration;
  if (tag === "u") next.textDecoration = addTextDecoration(next.textDecoration, "underline");
  if (["s", "strike", "del"].includes(tag)) next.textDecoration = addTextDecoration(next.textDecoration, "line-through");
  applyTextDecorationDetails(next, textDecoration, textDecorationColor, textDecorationThickness, 14);
  if (tag === "sup") next.baselineShift = "super";
  if (tag === "sub") next.baselineShift = "sub";
  const inlineShift = inlineBaselineShift(verticalAlign);
  if (inlineShift) next.baselineShift = inlineShift;
  if (letterSpacing != null) next.letterSpacing = normalizeSpacingLength(letterSpacing, next.fontSize ?? 14);
  if (direction != null) next.direction = normalizeTextDirection(direction);
  return next;
}

function htmlFontSize(value: string | null): number | null {
  if (!value) return null;
  const normalized = value.trim();
  if (!normalized) return null;
  if (normalized.startsWith("+")) return 24;
  if (normalized.startsWith("-")) return 12;
  const parsed = Number.parseInt(normalized, 10);
  if (!Number.isFinite(parsed)) return null;
  return [10, 13, 16, 18, 24, 32, 48][Math.max(1, Math.min(7, parsed)) - 1] ?? null;
}

function htmlFontWeightIsNormal(value: string | null | undefined): boolean {
  const normalized = (value ?? "normal").trim().toLowerCase();
  return normalized === "normal" || normalized === "400";
}

function htmlFontStyleIsNormal(value: string | null | undefined): boolean {
  return (value ?? "normal").trim().toLowerCase() === "normal";
}

function addTextDecoration(current: string | undefined, token: string): string {
  const tokens = (current || "").toLowerCase().split(/\s+/).filter(Boolean);
  return tokens.includes(token) ? (current || token) : `${current || ""} ${token}`.trim();
}

function inlineBaselineShift(value: string | null): string | null {
  const normalized = value?.trim().toLowerCase();
  return normalized === "super" || normalized === "sub" ? normalized : null;
}

function htmlSideBorder(declarations: Record<string, string>, side: string, fallback: TableBorder, style: SvgStyle): TableBorder | null {
  const shorthand = declarations[`border-${side}`];
  const sideStyle = declarations[`border-${side}-style`];
  const sideWidth = declarations[`border-${side}-width`];
  const sideColor = declarations[`border-${side}-color`];
  if (!shorthand && !sideStyle && !sideWidth && !sideColor) return null;
  const parsed = parseHtmlBorder(shorthand ?? [sideWidth, sideStyle, sideColor].filter(Boolean).join(" "), style);
  return {
    ...fallback,
    stroke: parsed.stroke,
    strokeAlpha: parsed.strokeAlpha,
    strokeWidth: parsed.strokeWidth,
    strokeDasharray: parsed.strokeDasharray,
    compound: parsed.compound,
  };
}

function parseHtmlBorder(value: string | null, style: SvgStyle): TableBorder {
  if (!value || htmlBorderIsNone(value)) return { stroke: null, strokeAlpha: null, strokeWidth: 0, strokeLineCap: null, strokeLineJoin: null, strokeMiterlimit: null, strokeDasharray: null, compound: null };
  const parts = cssValueTokens(value);
  const width = parts.map((part) => htmlCssLength(part, style.fontSize ?? rootFontSize)).find((item): item is number => item != null) ?? null;
  const colorPart = parts.find((part) => parseCssColor(part, style));
  const stylePart = parts.find((part) => ["dashed", "dotted", "double"].includes(part.toLowerCase()))?.toLowerCase() || null;
  const borderWidth = width ?? 1;
  const dasharray = htmlBorderDasharray(stylePart, borderWidth);
  return {
    stroke: colorPart ? parseCssColor(colorPart, style) : (style.stroke ?? "#000000"),
    strokeAlpha: colorPart ? cssColorAlpha(colorPart) : (style.strokeAlpha ?? null),
    strokeWidth: borderWidth,
    ...strokeStyle(style),
    strokeDasharray: dasharray,
    compound: stylePart === "double" ? "dbl" : null,
  };
}

function htmlBorderIsNone(value: string): boolean {
  return cssValueTokens(value).some((token) => ["none", "hidden"].includes(token.replace(/,$/, "").toLowerCase()));
}

function applyHtmlBorderStyle(style: SvgStyle, value: string): void {
  const stylePart = value.trim().toLowerCase().split(/\s+/).find((part) => ["none", "hidden", "solid", "dashed", "dotted", "double"].includes(part));
  if (!stylePart) return;
  if (["none", "hidden"].includes(stylePart)) {
    style.stroke = null;
    style.strokeAlpha = null;
    style.strokeWidth = 0;
    style.strokeDasharray = null;
    style.tableBorderCompound = null;
    return;
  }
  const width = style.strokeWidth ?? 1;
  style.strokeDasharray = htmlBorderDasharray(stylePart, width);
  style.tableBorderCompound = stylePart === "double" ? "dbl" : null;
}

function htmlBorderDasharray(stylePart: string | null, width: number): string | null {
  if (stylePart === "dashed") return `${width * 1.5} ${width * 1.5}`;
  if (stylePart === "dotted") return `${width / 3} ${width / 3}`;
  return null;
}

function normalizeHtmlTextAlign(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (["left", "start"].includes(normalized)) return "start";
  if (["center", "middle"].includes(normalized)) return "middle";
  if (["right", "end"].includes(normalized)) return "end";
  return null;
}

function normalizeHtmlVerticalAlign(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (["top", "text-top"].includes(normalized)) return "top";
  if (["middle", "center"].includes(normalized)) return "middle";
  if (["bottom", "text-bottom"].includes(normalized)) return "bottom";
  return null;
}

function htmlCssLength(value: string | null, basis: number): number | null {
  if (!value) return null;
  const trimmed = value.trim().toLowerCase();
  if (!trimmed || trimmed === "auto") return null;
  if (trimmed === "thin") return 1;
  if (trimmed === "medium") return 3;
  if (trimmed === "thick") return 5;
  const parsed = parseCssLength(trimmed, basis, Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function htmlFirstColorFill(value: string | null, style: SvgStyle): HtmlFill | null {
  const token = cssValueTokens(value || "").find((item) => parseCssColor(item.replace(/,$/, ""), style) != null);
  if (!token) return null;
  const normalized = token.replace(/,$/, "");
  const color = parseCssColor(normalized, style);
  return color == null ? null : { color, alpha: cssColorAlpha(normalized) };
}

function htmlPaddingSides(value: string | null): { top: number; right: number; bottom: number; left: number } | null {
  if (!value) return null;
  const tokens = cssValueTokens(value).slice(0, 4);
  if (!tokens.length) return null;
  const lengths = tokens.map((token) => htmlCssLength(token, 0));
  if (lengths.some((length) => length == null)) return null;
  const top = lengths[0] as number;
  const right = (lengths[1] ?? top) as number;
  const bottom = (lengths[2] ?? top) as number;
  const left = (lengths[3] ?? right) as number;
  return { top, right, bottom, left };
}

function htmlWhiteSpaceWrap(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return ["nowrap", "pre", "pre-line", "pre-wrap"].includes(normalized) ? "none" : null;
}

function htmlStyleValue(element: Element, name: string): string | null {
  return styleDeclarations(element.getAttribute("style"))[name] ?? null;
}

function htmlCssValue(element: Element, name: string, css: CssRule[]): string | null {
  return resolvedCascadedDeclarations(element, css, {}, htmlAttributeAliases(element))[name] ?? null;
}

function htmlAttributeAliases(element: Element): Record<string, string> {
  const aliases: Record<string, string> = {
    align: "text-align",
    valign: "vertical-align",
    bgcolor: "background-color",
    border: "border",
    bordercolor: "border-color",
    cellpadding: "padding",
    cellspacing: "border-spacing",
  };
  if (element.hasAttribute("nowrap")) aliases.nowrap = "white-space";
  return aliases;
}

function htmlCellText(cell: Element): string {
  return (cell.textContent || "").replace(/\s+/g, " ").trim();
}

function htmlTextRuns(element: Element, inheritedStyle: SvgStyle, css: CssRule[]): TextRun[] {
  const runs: TextRun[] = [];
  let breakBefore = false;
  const appendText = (text: string, style: SvgStyle) => {
    const normalized = text.replace(/\s+/g, " ");
    if (!normalized.trim()) {
      if (runs.length && !breakBefore) runs.push({ ...htmlTextRun(" ", style), breakBefore: false });
      return;
    }
    runs.push({ ...htmlTextRun(normalized, style), breakBefore });
    breakBefore = false;
  };
  const appendNode = (node: Node, style: SvgStyle) => {
    if (node.nodeType === Node.TEXT_NODE) {
      appendText(node.textContent || "", style);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const child = node as Element;
    const tag = localName(child);
    if (tag === "br") {
      breakBefore = true;
      return;
    }
    const childStyle = htmlElementStyle(child, style, css);
    if (["div", "p", "li"].includes(tag) && runs.length) breakBefore = true;
    for (const item of Array.from(child.childNodes)) appendNode(item, childStyle);
    if (["div", "p", "li"].includes(tag)) breakBefore = true;
  };
  for (const node of Array.from(element.childNodes)) {
    appendNode(node, inheritedStyle);
  }
  return trimHtmlTextRuns(runs);
}

function htmlTextRun(text: string, style: SvgStyle): TextRun {
  const transformed = applyTextTransform(text, style.textTransform);
  const fontSize = style.fontSize ?? 14;
  return {
    text: transformed,
    breakBefore: false,
    preserveSpace: false,
    fill: style.color ?? style.fill ?? "#000000",
    fillAlpha: style.color ? (style.colorAlpha ?? null) : (style.fillAlpha ?? null),
    stroke: style.stroke ?? null,
    strokeAlpha: style.strokeAlpha ?? null,
    strokeWidth: style.strokeWidth ?? 1,
    ...strokeStyle(style),
    fontSize,
    fontFamily: style.fontFamily || "Aptos",
    bold: ["bold", "700", "800", "900"].includes(style.fontWeight || ""),
    italic: isItalic(style),
    fontVariant: style.fontVariant ?? null,
    underline: hasUnderline(style),
    underlineStyle: underlineStyle(style),
    underlineColor: style.textDecorationColor ?? null,
    underlineAlpha: style.textDecorationAlpha ?? null,
    underlineThickness: style.textDecorationThickness ?? null,
    strike: hasStrike(style),
    baselineShift: style.baselineShift ?? null,
    letterSpacing: effectiveLetterSpacing(style, transformed, fontSize),
  };
}

function underlineStyle(style: SvgStyle): string | null {
  const decoration = style.textDecoration || "";
  if (decoration.includes("wavy")) return "wavy";
  if (decoration.includes("dashed")) return "dashed";
  if (decoration.includes("dotted")) return "dotted";
  if (decoration.includes("double")) return "double";
  return null;
}

function trimHtmlTextRuns(runs: TextRun[]): TextRun[] {
  let first = -1;
  let last = -1;
  for (let index = 0; index < runs.length; index += 1) {
    if (runs[index]?.text.trim()) {
      first = index;
      break;
    }
  }
  for (let index = runs.length - 1; index >= 0; index -= 1) {
    if (runs[index]?.text.trim()) {
      last = index;
      break;
    }
  }
  if (first < 0 || last < 0) return [];
  return runs.slice(first, last + 1).map((run, index, sliced) => ({
    ...run,
    text: index === 0 ? run.text.trimStart() : index === sliced.length - 1 ? run.text.trimEnd() : run.text,
  })).filter((run) => run.text.length > 0);
}

function textRuns(element: Element, inheritedStyle: SvgStyle, viewport: Viewport = defaultViewport(), metricScale = 1, css: CssRule[] = [], refs: Map<string, Element> = new Map()): TextRun[] {
  const runs: TextRun[] = [];
  const rootPreserveSpace = xmlSpacePreserve(element);
  const append = (text: string, style: SvgStyle, preserveSpace: boolean, breakBefore = false) => {
    if (!text) return;
    const runStyle = scaledTextMetricsStyle(style, metricScale);
    const transformed = applyTextTransform(text, style.textTransform);
    runs.push({
      text: transformed,
      breakBefore,
      preserveSpace,
      fill: runStyle.fill ?? "#111827",
      fillAlpha: runStyle.fillAlpha ?? null,
      stroke: runStyle.stroke ?? null,
      strokeAlpha: runStyle.strokeAlpha ?? null,
      strokeWidth: runStyle.strokeWidth ?? 1,
      ...strokeStyle(runStyle),
      fontSize: runStyle.fontSize ?? (inheritedStyle.fontSize == null ? 18 : inheritedStyle.fontSize * metricScale),
      fontFamily: runStyle.fontFamily || inheritedStyle.fontFamily || "Aptos",
      bold: ["bold", "700", "800", "900"].includes(runStyle.fontWeight || ""),
      italic: isItalic(runStyle),
      fontVariant: runStyle.fontVariant ?? null,
      underline: hasUnderline(runStyle),
      underlineStyle: underlineStyle(runStyle),
      underlineColor: runStyle.textDecorationColor ?? null,
      underlineAlpha: runStyle.textDecorationAlpha ?? null,
      underlineThickness: runStyle.textDecorationThickness ?? null,
      strike: hasStrike(runStyle),
      baselineShift: runStyle.baselineShift ?? null,
      letterSpacing: effectiveLetterSpacing(runStyle, transformed, runStyle.fontSize ?? (inheritedStyle.fontSize == null ? 18 : inheritedStyle.fontSize * metricScale)),
    });
  };
  for (const node of Array.from(element.childNodes)) {
    if (node.nodeType === Node.TEXT_NODE) {
      append(node.textContent || "", inheritedStyle, rootPreserveSpace);
    } else if (node.nodeType === Node.ELEMENT_NODE && localName(node as Element) === "tspan") {
      const tspan = node as Element;
      const style = computedStyle(tspan, inheritedStyle, css, refs, viewport);
      const preserveSpace = rootPreserveSpace || xmlSpacePreserve(tspan);
      append((node.textContent || ""), style, preserveSpace, runs.length > 0 && tspanStartsNewLine(tspan, viewport, css, inheritedStyle));
    }
  }
  if (!runs.length) append(element.textContent || "", inheritedStyle, rootPreserveSpace);
  const first = runs.findIndex((run) => run.text.trim());
  let last = -1;
  for (let index = runs.length - 1; index >= 0; index -= 1) {
    if (runs[index]?.text.trim()) {
      last = index;
      break;
    }
  }
  if (first < 0 || last < 0) return [];
  return runs.slice(first, last + 1).map((run, index, sliced) => ({
    ...run,
    text: run.preserveSpace ? run.text : index === 0 ? run.text.trimStart() : index === sliced.length - 1 ? run.text.trimEnd() : run.text,
  })).filter((run) => run.text.length > 0);
}

function svgTextPosition(element: Element, viewport: Viewport, css: CssRule[] = [], inheritedStyle: SvgStyle = {}): [number, number] {
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
  let x = optionalCascadedGeom(element, declarations, "x", "x", viewport);
  let y = optionalCascadedGeom(element, declarations, "y", "y", viewport);
  let dx = firstOptionalCascadedGeom(element, declarations, "dx", "x", viewport);
  let dy = firstOptionalCascadedGeom(element, declarations, "dy", "y", viewport);
  if (x != null && y != null) return [x + (dx ?? 0), y + (dy ?? 0)];
  for (const child of Array.from(element.children)) {
    if (localName(child) !== "tspan") continue;
    const childDeclarations = resolvedCascadedDeclarations(child, css, inheritedStyle);
    x ??= optionalCascadedGeom(child, childDeclarations, "x", "x", viewport);
    y ??= optionalCascadedGeom(child, childDeclarations, "y", "y", viewport);
    dx ??= firstOptionalCascadedGeom(child, childDeclarations, "dx", "x", viewport);
    dy ??= firstOptionalCascadedGeom(child, childDeclarations, "dy", "y", viewport);
    if (x != null && y != null) break;
  }
  return [(x ?? 0) + (dx ?? 0), (y ?? 0) + (dy ?? 0)];
}

function firstPositionedTspanAnchor(element: Element, inheritedStyle: SvgStyle, css: CssRule[] = [], refs: Map<string, Element> = new Map(), viewport: Viewport = defaultViewport()): string | null {
  if (element.hasAttribute("x") || element.hasAttribute("y") || (element.childNodes[0]?.nodeType === Node.TEXT_NODE && (element.childNodes[0].textContent || "").trim())) return null;
  const first = firstTextTspan(element);
  if (!first || !first.hasAttribute("x") || !first.hasAttribute("y")) return null;
  return computedStyle(first, inheritedStyle, css, refs, viewport).textAnchor ?? null;
}

function firstPositionedTspanBaseline(element: Element, inheritedStyle: SvgStyle, css: CssRule[] = [], refs: Map<string, Element> = new Map(), viewport: Viewport = defaultViewport()): string | null {
  if (element.hasAttribute("x") || element.hasAttribute("y") || (element.childNodes[0]?.nodeType === Node.TEXT_NODE && (element.childNodes[0].textContent || "").trim())) return null;
  const first = firstTextTspan(element);
  if (!first || !first.hasAttribute("x") || !first.hasAttribute("y")) return null;
  return computedStyle(first, inheritedStyle, css, refs, viewport).textBaseline ?? null;
}

function firstTextTspan(element: Element): Element | null {
  for (const child of Array.from(element.children)) {
    if (localName(child) === "tspan" && (child.textContent || "").trim()) return child;
  }
  return null;
}

function tspanStartsNewLine(tspan: Element, viewport: Viewport, css: CssRule[] = [], inheritedStyle: SvgStyle = {}): boolean {
  const declarations = resolvedCascadedDeclarations(tspan, css, inheritedStyle);
  if (cascadedGeomValue(tspan, declarations, "x") != null || cascadedGeomValue(tspan, declarations, "y") != null) return true;
  const dy = firstOptionalCascadedGeom(tspan, declarations, "dy", "y", viewport);
  return dy != null && Math.abs(dy) > 0.001;
}

function xmlSpacePreserve(element: Element): boolean {
  return element.getAttribute("xml:space") === "preserve" || element.getAttributeNS("http://www.w3.org/XML/1998/namespace", "space") === "preserve";
}

function isItalic(style: SvgStyle): boolean {
  const value = (style.fontStyle || "").trim().toLowerCase();
  return value === "italic" || value.startsWith("oblique");
}

function hasUnderline(style: SvgStyle): boolean {
  return (style.textDecoration || "").toLowerCase().split(/\s+/).includes("underline");
}

function hasStrike(style: SvgStyle): boolean {
  return (style.textDecoration || "").toLowerCase().split(/\s+/).includes("line-through");
}

function hasVisibleTextDecoration(style: SvgStyle): boolean {
  return hasUnderline(style) || hasStrike(style);
}

function hasOnlyVisibleUnderline(style: SvgStyle): boolean {
  return hasUnderline(style) && !hasStrike(style);
}

function applyTextDecorationDetails(style: SvgStyle, decoration: string | null, colorValue: string | null, thicknessValue: string | null, basis: number): void {
  if (!hasUnderline(style)) return;
  const colorToken = colorValue ?? textDecorationColorToken(decoration);
  if (colorToken) {
    const color = parseCssColor(colorToken, style);
    if (color) {
      style.textDecorationColor = color;
      style.textDecorationAlpha = cssColorAlpha(colorToken);
    }
  }
  if (hasStrike(style)) return;
  const thicknessToken = thicknessValue ?? textDecorationThicknessToken(decoration);
  if (!thicknessToken) return;
  const normalized = thicknessToken.trim().toLowerCase();
  if (!normalized || normalized === "auto" || normalized === "from-font") return;
  const thickness = parseCssLength(normalized, basis, Number.NaN);
  if (Number.isFinite(thickness)) style.textDecorationThickness = Math.max(0, thickness);
}

function textDecorationColorToken(value: string | null): string | null {
  if (!value) return null;
  for (const token of cssValueTokens(value)) {
    const normalized = token.toLowerCase();
    if (textDecorationLineTokens.has(normalized) || textDecorationStyleTokens.has(normalized) || normalized === "auto" || normalized === "from-font" || htmlCssLength(normalized, 0) != null) {
      continue;
    }
    if (normalized === "currentcolor" || parseCssColor(token, {})) return token;
  }
  return null;
}

function textDecorationThicknessToken(value: string | null): string | null {
  if (!value) return null;
  for (const token of cssValueTokens(value)) {
    const normalized = token.toLowerCase();
    if (normalized === "auto" || normalized === "from-font") return token;
    if (textDecorationLineTokens.has(normalized) || textDecorationStyleTokens.has(normalized) || normalized === "currentcolor" || parseCssColor(token, {})) {
      continue;
    }
    if (htmlCssLength(normalized, 0) != null) return token;
  }
  return null;
}

const textDecorationLineTokens = new Set(["underline", "overline", "line-through", "blink", "none"]);
const textDecorationStyleTokens = new Set(["solid", "double", "dotted", "dashed", "wavy"]);

function normalizeFontVariant(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return normalized === "small-caps" || normalized === "all-small-caps" ? normalized : null;
}

function normalizeTextDirection(value: string): string | null {
  return value.trim().toLowerCase() === "rtl" ? "rtl" : null;
}

function normalizeTextTransform(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === "none" || normalized === "normal") return null;
  return ["uppercase", "lowercase", "capitalize"].includes(normalized) ? normalized : null;
}

function applyTextTransform(text: string, value: string | null | undefined): string {
  if (value === "uppercase") return text.toUpperCase();
  if (value === "lowercase") return text.toLowerCase();
  if (value === "capitalize") return text.replace(/(^|[\s\-_])(\S)/g, (_match, prefix: string, char: string) => `${prefix}${char.toUpperCase()}`);
  return text;
}

function normalizeTextAnchor(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return ["start", "middle", "end"].includes(normalized) ? normalized : null;
}

function normalizeTextBaseline(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === "middle" || normalized === "central") return "middle";
  if (normalized === "text-after-edge" || normalized === "ideographic") return "text-after-edge";
  if (normalized === "text-before-edge" || normalized === "hanging") return "text-before-edge";
  return null;
}

function normalizeBaselineShift(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return normalized === "super" || normalized === "sub" ? normalized : null;
}

function normalizeLengthAdjust(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return normalized === "spacing" || normalized === "spacingandglyphs" ? normalized : null;
}

function effectiveLetterSpacing(style: SvgStyle, text: string, fontSize: number): number | null {
  if (style.letterSpacing != null) return style.letterSpacing;
  const line = text.trim();
  if (style.textLength != null && (style.lengthAdjust == null || style.lengthAdjust === "spacing" || style.lengthAdjust === "spacingandglyphs") && line.length > 1 && !text.includes("\n")) {
    const naturalWidth = fontSize * line.length * 0.9;
    return (style.textLength - naturalWidth) / (line.length - 1);
  }
  if (style.wordSpacing != null && line.length > 1 && !text.includes("\n")) {
    const gaps = wordGapCount(line);
    if (gaps > 0) return (style.wordSpacing * gaps) / (line.length - 1);
  }
  return null;
}

function wordSpacingExtra(style: SvgStyle, text: string): number {
  return style.wordSpacing != null ? style.wordSpacing * wordGapCount(text) : 0;
}

function wordGapCount(text: string): number {
  return (text.trim().match(/[ \t\f\v]+/g) || []).length;
}

function singleTextRotation(value: string | null, text: string | null = null): number | null {
  if (!value) return null;
  const values = value.replaceAll(",", " ").trim().split(/\s+/).filter(Boolean).map(parseAngle);
  if (!values.length || values.some((item) => item == null)) return null;
  const first = values[0]!;
  if (values.some((item) => Math.abs((item ?? 0) - first) > 0.0001) && (!text || text.length > 1)) return null;
  return first;
}

function textRotation(element: Element, style: SvgStyle, css: CssRule[] = [], refs: Map<string, Element> = new Map(), viewport: Viewport = defaultViewport()): number | null {
  if (style.rotate != null) return style.rotate;
  for (const child of Array.from(element.children)) {
    if (localName(child) !== "tspan") continue;
    const childStyle = computedStyle(child, style, css, refs, viewport);
    if (childStyle.rotate != null) return childStyle.rotate;
  }
  return null;
}

function parseAngle(value: string): number | null {
  const normalized = value.trim().toLowerCase();
  const parsed = Number.parseFloat(normalized);
  if (!Number.isFinite(parsed)) return null;
  if (normalized.endsWith("turn")) return parsed * 360;
  if (normalized.endsWith("rad")) return (parsed * 180) / Math.PI;
  if (normalized.endsWith("grad")) return parsed * 0.9;
  return parsed;
}

function markRelationConnectors(shapes: Shape[]): void {
  const boxes = shapes.filter((shape): shape is RectShape | EllipseShape | TextShape | FreeformShape => ["rect", "ellipse", "text", "freeform"].includes(shape.kind));
  for (const line of shapes.filter((shape): shape is LineShape => shape.kind === "line" && shape.relation)) {
    line.startId = nearestShapeId(line.x1, line.y1, boxes);
    line.endId = nearestShapeId(line.x2, line.y2, boxes);
  }
}

function nearestShapeId(x: number, y: number, shapes: (RectShape | EllipseShape | TextShape | FreeformShape)[]): number | null {
  if (!shapes.length) return null;
  return shapes
    .map((shape) => {
      const box = shapeBox(shape);
      const dx = Math.max(box.x - x, 0, x - (box.x + box.width));
      const dy = Math.max(box.y - y, 0, y - (box.y + box.height));
      return { id: shape.id, distance: dx * dx + dy * dy };
    })
    .sort((a, b) => a.distance - b.distance)[0]?.id ?? null;
}

function shapeBox(shape: RectShape | EllipseShape | TextShape | FreeformShape): Box {
  if (shape.kind === "freeform") {
    const xs = shape.points.map(([x]) => x);
    const ys = shape.points.map(([, y]) => y);
    const minX = Math.min(...xs);
    const minY = Math.min(...ys);
    return { x: minX, y: minY, width: Math.max(...xs) - minX, height: Math.max(...ys) - minY };
  }
  return { x: shape.x, y: shape.y, width: shape.width, height: shape.height };
}

function rectClipBounds(shape: Shape | null, style: SvgStyle, refs: Map<string, Element>, matrix: Matrix, viewport: Viewport = defaultViewport(), css: CssRule[] = []): Box | null {
  if (!style.clipPath || style.clipPath === "none") return null;
  const refId = urlRef(style.clipPath);
  if (!refId) return null;
  const clip = refs.get(refId);
  if (!clip || localName(clip) !== "clipPath") return null;
  const units = normalizedClipPathUnits(clip);
  const rect = Array.from(clip.children).find((child) => localName(child) === "rect");
  if (!rect) return null;
  const clipStyle = computedStyle(clip, style, css, refs, viewport);
  const rectStyle = computedStyle(rect, clipStyle, css, refs, viewport);
  const declarations = resolvedCascadedDeclarations(rect, css, rectStyle);
  const width = units === "objectboundingbox" ? bboxCascadedGeom(rect, declarations, "width") : cascadedGeom(rect, declarations, "width", "x", viewport);
  const height = units === "objectboundingbox" ? bboxCascadedGeom(rect, declarations, "height") : cascadedGeom(rect, declarations, "height", "y", viewport);
  if (width <= 0 || height <= 0) return null;
  if (units === "objectboundingbox") {
    const box = clipTargetBox(shape);
    if (!box || clipStyle.transform || rectStyle.transform) return null;
    return {
      x: box.x + bboxCascadedGeom(rect, declarations, "x") * box.width,
      y: box.y + bboxCascadedGeom(rect, declarations, "y") * box.height,
      width: width * box.width,
      height: height * box.height,
    };
  }
  if (units !== "userspaceonuse") return null;
  const clipMatrix = multiply(multiply(matrix, transformMatrix(clipStyle.transform ?? clip.getAttribute("transform"))), transformMatrix(rectStyle.transform ?? rect.getAttribute("transform")));
  if (!matrixKeepsRectAxisAligned(clipMatrix)) return null;
  const box = transformedBox(clipMatrix, cascadedGeom(rect, declarations, "x", "x", viewport), cascadedGeom(rect, declarations, "y", "y", viewport), width, height);
  return box.width > 0 && box.height > 0 ? box : null;
}

function normalizedClipPathUnits(clip: Element): string {
  const units = (clip.getAttribute("clipPathUnits") || "userSpaceOnUse").trim().toLowerCase();
  return units === "objectboundingbox" ? "objectboundingbox" : units === "userspaceonuse" ? "userspaceonuse" : "";
}

function svgViewportClip(element: Element, style: SvgStyle, positionedMatrix: Matrix, viewport: Viewport): Box | null {
  if (style.overflow !== "hidden") return null;
  const box = transformedBox(positionedMatrix, 0, 0, viewport.width, viewport.height);
  return box.width > 0 && box.height > 0 ? box : null;
}

function combineClips(a: Box | null, b: Box | null): Box | null {
  if (a && b) return intersectBox(a, b);
  return a ?? b;
}

function clipTargetBox(shape: Shape | null): Box | null {
  if (!shape) return null;
  if (shape.kind === "rect" || shape.kind === "ellipse" || shape.kind === "text" || shape.kind === "image") {
    return { x: shape.x, y: shape.y, width: shape.width, height: shape.height };
  }
  if (shape.kind === "line") {
    const x = Math.min(shape.x1, shape.x2);
    const y = Math.min(shape.y1, shape.y2);
    return { x, y, width: Math.abs(shape.x2 - shape.x1), height: Math.abs(shape.y2 - shape.y1) };
  }
  if (shape.kind === "freeform") return shapeBox(shape);
  return null;
}

function applyClip(shape: Shape | null, clip: Box | null): Shape | null {
  if (!shape || !clip) return shape;
  if (shape.kind === "rect") {
    const box = intersectBox(shape, clip);
    return box ? { ...shape, ...box, rx: Math.min(shape.rx, box.width / 2, box.height / 2) } : null;
  }
  if (shape.kind === "ellipse" || shape.kind === "text" || shape.kind === "image") {
    const box = intersectBox(shape, clip);
    return box ? { ...shape, ...box } : null;
  }
  if (shape.kind === "line") {
    const clipped = clipSegmentToBox([shape.x1, shape.y1], [shape.x2, shape.y2], clip);
    return clipped ? { ...shape, x1: clipped[0][0], y1: clipped[0][1], x2: clipped[1][0], y2: clipped[1][1] } : null;
  }
  if (shape.kind === "freeform") {
    const bounds = shapeBox(shape);
    if (!intersectBox(bounds, clip)) return null;
    if (!shape.closed && shape.points.length === 2) {
      const clipped = clipSegmentToBox(shape.points[0]!, shape.points[1]!, clip);
      return clipped ? { ...shape, points: clipped } : null;
    }
    return { ...shape, points: shape.points.map(([x, y]) => [clamp(x, clip.x, clip.x + clip.width), clamp(y, clip.y, clip.y + clip.height)]) };
  }
  return shape;
}

function intersectBox(a: Box, b: Box): Box | null {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.width, b.x + b.width);
  const y2 = Math.min(a.y + a.height, b.y + b.height);
  if (x2 <= x1 || y2 <= y1) return null;
  return { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
}

function clipSegmentToBox(start: [number, number], end: [number, number], box: Box): [[number, number], [number, number]] | null {
  const dx = end[0] - start[0];
  const dy = end[1] - start[1];
  let t0 = 0;
  let t1 = 1;
  const checks: [number, number][] = [
    [-dx, start[0] - box.x],
    [dx, box.x + box.width - start[0]],
    [-dy, start[1] - box.y],
    [dy, box.y + box.height - start[1]],
  ];
  for (const [p, q] of checks) {
    if (p === 0 && q < 0) return null;
    if (p === 0) continue;
    const r = q / p;
    if (p < 0) t0 = Math.max(t0, r);
    else t1 = Math.min(t1, r);
    if (t0 > t1) return null;
  }
  return [
    [start[0] + t0 * dx, start[1] + t0 * dy],
    [start[0] + t1 * dx, start[1] + t1 * dy],
  ];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function urlRef(value: string): string | null {
  const match = value.match(/^url\(\s*['"]?#([^'")\s]+)['"]?\s*\)$/);
  return match?.[1] ?? null;
}

function shapeToXml(shape: Shape): string {
  if (shape.kind === "rect") return rectXml(shape);
  if (shape.kind === "ellipse") return ellipseXml(shape);
  if (shape.kind === "line") return shape.relation ? connectorXml(shape) : lineXml(shape);
  if (shape.kind === "text") return textXml(shape);
  if (shape.kind === "freeform") return freeformXml(shape);
  if (shape.kind === "image") return imageXml(shape);
  return tableXml(shape);
}

function rectXml(shape: RectShape): string {
  return spXml(shape.id, shape.name, shape.x, shape.y, shape.width, shape.height, shape.rx ? "roundRect" : "rect", fillXml(shape.fill, shape.fillAlpha) + lineStyleXml(shape.stroke, shape.strokeWidth, lineOptions(shape)), "");
}

function ellipseXml(shape: EllipseShape): string {
  return spXml(shape.id, shape.name, shape.x, shape.y, shape.width, shape.height, "ellipse", fillXml(shape.fill, shape.fillAlpha) + lineStyleXml(shape.stroke, shape.strokeWidth, lineOptions(shape)), "");
}

function lineXml(shape: LineShape): string {
  const x = Math.min(shape.x1, shape.x2);
  const y = Math.min(shape.y1, shape.y2);
  const width = Math.max(Math.abs(shape.x2 - shape.x1), 1);
  const height = Math.max(Math.abs(shape.y2 - shape.y1), 1);
  return spXml(shape.id, shape.name, x, y, width, height, "line", `<a:noFill/>${lineStyleXml(shape.stroke, shape.strokeWidth, lineOptions(shape, { head: shape.markerEnd, tail: shape.markerStart }))}`, "", null, lineXfrmAttrs(shape));
}

function connectorXml(shape: LineShape): string {
  const x = Math.min(shape.x1, shape.x2);
  const y = Math.min(shape.y1, shape.y2);
  const width = Math.max(Math.abs(shape.x2 - shape.x1), 1);
  const height = Math.max(Math.abs(shape.y2 - shape.y1), 1);
  const cxn = `${shape.startId ? `<a:stCxn id="${shape.startId}" idx="0"/>` : ""}${shape.endId ? `<a:endCxn id="${shape.endId}" idx="0"/>` : ""}`;
  return `<p:cxnSp><p:nvCxnSpPr><p:cNvPr id="${shape.id}" name="${xml(shape.name)}"/><p:cNvCxnSpPr>${cxn}</p:cNvCxnSpPr><p:nvPr/></p:nvCxnSpPr><p:spPr><a:xfrm${lineXfrmAttrs(shape)}><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(width)}" cy="${emu(height)}"/></a:xfrm><a:prstGeom prst="line"><a:avLst/></a:prstGeom><a:noFill/>${lineStyleXml(shape.stroke, shape.strokeWidth, lineOptions(shape, { head: true, tail: shape.markerStart }))}</p:spPr></p:cxnSp>`;
}

function lineXfrmAttrs(shape: LineShape): string {
  const flipH = shape.x2 < shape.x1 ? ' flipH="1"' : "";
  const flipV = shape.y2 < shape.y1 ? ' flipV="1"' : "";
  return `${flipH}${flipV}`;
}

function textXml(shape: TextShape): string {
  const runs = (shape.runs.length ? shape.runs : [{
    text: shape.text,
    breakBefore: false,
    preserveSpace: false,
    fill: shape.fill,
    fillAlpha: null,
    stroke: shape.stroke,
    strokeAlpha: shape.strokeAlpha,
    strokeWidth: shape.strokeWidth,
    strokeLineCap: shape.strokeLineCap,
    strokeLineJoin: shape.strokeLineJoin,
    strokeMiterlimit: shape.strokeMiterlimit,
    strokeDasharray: shape.strokeDasharray,
    fontSize: shape.fontSize,
    fontFamily: shape.fontFamily,
    bold: shape.bold,
    italic: shape.italic,
    fontVariant: shape.fontVariant,
    underline: shape.underline,
    underlineStyle: shape.underlineStyle,
    underlineColor: shape.underlineColor,
    underlineAlpha: shape.underlineAlpha,
    underlineThickness: shape.underlineThickness,
    strike: shape.strike,
    baselineShift: shape.baselineShift,
    letterSpacing: shape.letterSpacing,
  }]).map(textRunXml).join("");
  const body = `<p:txBody><a:bodyPr wrap="none"${textBaselineAnchorXml(shape.baseline)}/><a:lstStyle/><a:p>${paragraphPropertiesXml(shape.anchor, shape.direction)}${runs}</a:p></p:txBody>`;
  return spXml(shape.id, shape.name, shape.x, shape.y, shape.width, shape.height, "rect", "<a:noFill/><a:ln><a:noFill/></a:ln>", body, shape.rotation);
}

function textRunXml(run: TextRun): string {
  const attrs = ` lang="en-US" sz="${Math.round(run.fontSize * 100)}"${run.bold ? ' b="1"' : ""}${run.italic ? ' i="1"' : ""}${fontVariantXml(run.fontVariant)}${underlineXml(run)}${run.strike ? ' strike="sngStrike"' : ""}${baselineShiftXml(run.baselineShift)}${letterSpacingXml(run.letterSpacing)}`;
  const parts = run.text.split(/\r\n|\r|\n/);
  const runProperties = `${solidColorXml(run.fill, run.fillAlpha)}${textOutlineXml(run)}${underlineChildrenXml(run)}<a:latin typeface="${xml(run.fontFamily)}"/>`;
  return `${run.breakBefore ? "<a:br/>" : ""}${parts.map((part, index) => `${index > 0 ? "<a:br/>" : ""}<a:r><a:rPr${attrs}>${runProperties}</a:rPr><a:t>${xml(part)}</a:t></a:r>`).join("")}`;
}

function textOutlineXml(run: TextRun): string {
  if (!run.stroke || run.strokeWidth <= 0) return "";
  return lineStyleXml(run.stroke, run.strokeWidth, lineOptions(run));
}

function underlineXml(run: TextRun): string {
  if (!run.underline) return "";
  if (run.underlineStyle === "dashed") return ' u="dash"';
  if (run.underlineStyle === "dotted") return ' u="dotted"';
  if (run.underlineStyle === "double") return ' u="dbl"';
  if (run.underlineStyle === "wavy") return ' u="wavy"';
  return ' u="sng"';
}

function underlineChildrenXml(run: TextRun): string {
  if (!run.underline) return "";
  const fill = run.underlineColor ? `<a:uFill>${solidColorXml(run.underlineColor, run.underlineAlpha)}</a:uFill>` : "";
  const line = run.underlineThickness != null ? `<a:uLn w="${emu(run.underlineThickness)}"/>` : "";
  return `${fill}${line}`;
}

function fontVariantXml(value: string | null): string {
  if (value === "small-caps") return ' cap="small"';
  if (value === "all-small-caps") return ' cap="all"';
  return "";
}

function baselineShiftXml(value: string | null): string {
  if (value === "super") return ' baseline="30000"';
  if (value === "sub") return ' baseline="-25000"';
  return "";
}

function letterSpacingXml(value: number | null): string {
  if (value == null || Math.abs(value) < 0.001) return "";
  return ` spc="${Math.round(value * 75)}"`;
}

function paragraphPropertiesXml(anchor: string | null, direction: string | null): string {
  const attrs: string[] = [];
  if (anchor === "middle") attrs.push('algn="ctr"');
  if (anchor === "end") attrs.push('algn="r"');
  if (direction === "rtl") attrs.push('rtl="1"');
  return attrs.length ? `<a:pPr ${attrs.join(" ")}/>` : "";
}

function textBaselineAnchorXml(baseline: string | null): string {
  if (baseline === "middle") return ' anchor="ctr"';
  if (baseline === "text-after-edge") return ' anchor="b"';
  if (baseline === "text-before-edge") return ' anchor="t"';
  return "";
}

function tableXml(shape: TableShape): string {
  const grid = shape.columns.map((width) => `<a:gridCol w="${emu(width)}"/>`).join("");
  const rows = shape.rows
    .map((height, rowIndex) => {
      const cells = shape.columns
        .map((_, colIndex) => {
          const cell = tableCellAt(shape.cells, rowIndex, colIndex);
          const attrs = tableCellAttrs(cell, rowIndex, colIndex);
          const origin = Boolean(cell && cell.row === rowIndex && cell.col === colIndex);
          const text = origin && cell?.text ? tableCellTextXml(cell) : "";
          const borders = origin ? tableBorderXml(cell) : "";
          return `<a:tc${attrs}><a:txBody>${tableCellBodyPrXml(cell)}<a:lstStyle/><a:p>${tableCellParagraphPrXml(cell)}${text}</a:p></a:txBody><a:tcPr>${fillXml(cell?.fill || "#ffffff", cell?.fillAlpha ?? null)}${borders}</a:tcPr></a:tc>`;
        })
        .join("");
      return `<a:tr h="${emu(height)}">${cells}</a:tr>`;
    })
    .join("");
  return `<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="${shape.id}" name="${xml(shape.name)}"/><p:cNvGraphicFramePr><a:graphicFrameLocks noGrp="1"/></p:cNvGraphicFramePr><p:nvPr/></p:nvGraphicFramePr><p:xfrm><a:off x="${emu(shape.x)}" y="${emu(shape.y)}"/><a:ext cx="${emu(shape.columns.reduce((a, b) => a + b, 0))}" cy="${emu(shape.rows.reduce((a, b) => a + b, 0))}"/></p:xfrm><a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table"><a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>${grid}</a:tblGrid>${rows}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>`;
}

function tableCellAt(cells: TableCell[], row: number, col: number): TableCell | null {
  return cells.find((cell) => row >= cell.row && row < cell.row + cell.rowSpan && col >= cell.col && col < cell.col + cell.colSpan) ?? null;
}

function tableCellAttrs(cell: TableCell | null, row: number, col: number): string {
  if (!cell) return "";
  const attrs: string[] = [];
  if (cell.row === row && cell.col === col) {
    if (cell.colSpan > 1) attrs.push(`gridSpan="${cell.colSpan}"`);
    if (cell.rowSpan > 1) attrs.push(`rowSpan="${cell.rowSpan}"`);
  } else {
    if (col > cell.col) attrs.push('hMerge="1"');
    if (row > cell.row) attrs.push('vMerge="1"');
  }
  return attrs.length ? ` ${attrs.join(" ")}` : "";
}

function tableCellTextXml(cell: TableCell): string {
  if (cell.runs.length) return cell.runs.map(textRunXml).join("");
  const attrs = ` lang="en-US" sz="1400"${cell.textBold ? ' b="1"' : ""}`;
  const fill = solidColorXml(cell.textFill || "#111827", cell.textFillAlpha);
  return `<a:r><a:rPr${attrs}>${fill}</a:rPr><a:t>${xml(cell.text)}</a:t></a:r>`;
}

function tableCellBodyPrXml(cell: TableCell | null): string {
  const left = emu(cell?.paddingLeft ?? 0);
  const right = emu(cell?.paddingRight ?? 0);
  const top = emu(cell?.paddingTop ?? 0);
  const bottom = emu(cell?.paddingBottom ?? 0);
  const anchor = tableVerticalAnchor(cell?.verticalAlign ?? null);
  const wrap = cell?.nowrap ? ' wrap="none"' : "";
  return `<a:bodyPr lIns="${left}" rIns="${right}" tIns="${top}" bIns="${bottom}"${wrap}${anchor}/>`;
}

function tableCellParagraphPrXml(cell: TableCell | null): string {
  const attrs: string[] = [];
  const align = tableHorizontalAlign(cell?.textAlign ?? null);
  if (align) attrs.push(`algn="${align}"`);
  if (cell?.direction === "rtl") attrs.push('rtl="1"');
  return attrs.length ? `<a:pPr ${attrs.join(" ")}/>` : "";
}

function tableHorizontalAlign(value: string | null): string | null {
  if (value === "middle") return "ctr";
  if (value === "end") return "r";
  return null;
}

function tableVerticalAnchor(value: string | null): string {
  if (value === "top") return ' anchor="t"';
  if (value === "bottom") return ' anchor="b"';
  if (value === "middle") return ' anchor="ctr"';
  return "";
}

function tableBorderXml(cell: TableCell | null): string {
  if (!cell) return "";
  return [
    tableBorderLineXml("lnL", cell.borderLeft),
    tableBorderLineXml("lnR", cell.borderRight),
    tableBorderLineXml("lnT", cell.borderTop),
    tableBorderLineXml("lnB", cell.borderBottom),
  ].join("");
}

function tableBorderLineXml(tag: string, border: TableBorder): string {
  const stroke = border.stroke;
  const cap = svgLineCapToDml(border.strokeLineCap);
  const capAttr = cap ? ` cap="${xml(cap)}"` : "";
  const compoundAttr = border.compound ? ` cmpd="${xml(border.compound)}"` : "";
  if (!stroke || border.strokeWidth <= 0) return `<a:${tag} w="0"${capAttr}${compoundAttr}><a:noFill/></a:${tag}>`;
  return `<a:${tag} w="${emu(border.strokeWidth)}"${capAttr}${compoundAttr}><a:solidFill><a:srgbClr val="${hex(stroke)}">${alphaXml(border.strokeAlpha)}</a:srgbClr></a:solidFill>${dashXml(border.strokeDasharray, border.strokeWidth)}${joinXml(border.strokeLineJoin, border.strokeMiterlimit)}</a:${tag}>`;
}

function freeformXml(shape: FreeformShape): string {
  const box = shapeBox(shape);
  const width = Math.max(box.width, 1);
  const height = Math.max(box.height, 1);
  const local = shape.points.map(([x, y]) => [emu(x - box.x), emu(y - box.y)]);
  const [first, ...rest] = local;
  if (!first) return "";
  const commands = [`<a:moveTo><a:pt x="${first[0]}" y="${first[1]}"/></a:moveTo>`]
    .concat(rest.map(([x, y]) => `<a:lnTo><a:pt x="${x}" y="${y}"/></a:lnTo>`))
    .concat(shape.closed ? ["<a:close/>"] : [])
    .join("");
  const geom = `<a:custGeom><a:avLst/><a:gdLst/><a:ahLst/><a:cxnLst/><a:rect l="l" t="t" r="r" b="b"/><a:pathLst><a:path w="${emu(width)}" h="${emu(height)}">${commands}</a:path></a:pathLst></a:custGeom>`;
  return `<p:sp><p:nvSpPr><p:cNvPr id="${shape.id}" name="${xml(shape.name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="${emu(box.x)}" y="${emu(box.y)}"/><a:ext cx="${emu(width)}" cy="${emu(height)}"/></a:xfrm>${geom}${fillXml(shape.fill, shape.fillAlpha)}${lineStyleXml(shape.stroke, shape.strokeWidth, lineOptions(shape, { head: shape.markerEnd, tail: shape.markerStart }))}</p:spPr></p:sp>`;
}

function imageXml(shape: ImageShape): string {
  const srcRect = shape.srcRect ? srcRectXml(shape.srcRect) : "";
  const rot = shape.rotation == null ? "" : ` rot="${Math.round(shape.rotation * 60000)}"`;
  const flipH = shape.flipH ? ' flipH="1"' : "";
  const flipV = shape.flipV ? ' flipV="1"' : "";
  return `<p:pic><p:nvPicPr><p:cNvPr id="${shape.id}" name="${xml(shape.name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="${xml(shape.href)}">${blipAlphaXml(shape.alpha)}</a:blip>${srcRect}<a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm${rot}${flipH}${flipV}><a:off x="${emu(shape.x)}" y="${emu(shape.y)}"/><a:ext cx="${emu(shape.width)}" cy="${emu(shape.height)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>`;
}

function srcRectXml(rect: [number, number, number, number]): string {
  const [left, top, right, bottom] = rect;
  const attrs = [
    left ? `l="${left}"` : "",
    top ? `t="${top}"` : "",
    right ? `r="${right}"` : "",
    bottom ? `b="${bottom}"` : "",
  ].filter(Boolean).join(" ");
  return attrs ? `<a:srcRect ${attrs}/>` : "";
}

function spXml(id: number, name: string, x: number, y: number, width: number, height: number, prst: string, style: string, body: string, rotation: number | null = null, xfrmAttrs = ""): string {
  const rot = rotation == null ? "" : ` rot="${Math.round(rotation * 60000)}"`;
  return `<p:sp><p:nvSpPr><p:cNvPr id="${id}" name="${xml(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm${rot}${xfrmAttrs}><a:off x="${emu(x)}" y="${emu(y)}"/><a:ext cx="${emu(width)}" cy="${emu(height)}"/></a:xfrm><a:prstGeom prst="${prst}"><a:avLst/></a:prstGeom>${style}</p:spPr>${body}</p:sp>`;
}

function fillXml(color: string | null, alpha: number | null = null): string {
  return color ? `<a:solidFill><a:srgbClr val="${hex(color)}">${alphaXml(alpha)}</a:srgbClr></a:solidFill>` : "<a:noFill/>";
}

function solidColorXml(color: string | null, alpha: number | null = null): string {
  return color ? `<a:solidFill><a:srgbClr val="${hex(color)}">${alphaXml(alpha)}</a:srgbClr></a:solidFill>` : "";
}

function lineStyleXml(color: string | null, width: number, options: LineOptions = {}): string {
  if (!color || width <= 0) return "<a:ln><a:noFill/></a:ln>";
  const cap = options.cap ? ` cap="${xml(options.cap)}"` : "";
  return `<a:ln w="${emu(width)}"${cap}><a:solidFill><a:srgbClr val="${hex(color)}">${alphaXml(options.alpha)}</a:srgbClr></a:solidFill>${dashXml(options.dasharray, width)}${joinXml(options.join, options.miterlimit)}${options.tail ? '<a:tailEnd type="triangle"/>' : ""}${options.head ? '<a:headEnd type="triangle"/>' : ""}</a:ln>`;
}

type LineOptions = {
  head?: boolean;
  tail?: boolean;
  cap?: string | null;
  join?: string | null;
  miterlimit?: number | null;
  dasharray?: string | null;
  alpha?: number | null;
};

function lineOptions(shape: { strokeLineCap: string | null; strokeLineJoin: string | null; strokeMiterlimit: number | null; strokeDasharray: string | null; strokeAlpha?: number | null }, arrows: { head?: boolean; tail?: boolean } = {}): LineOptions {
  return { ...arrows, cap: svgLineCapToDml(shape.strokeLineCap), join: shape.strokeLineJoin, miterlimit: shape.strokeMiterlimit, dasharray: shape.strokeDasharray, alpha: shape.strokeAlpha ?? null };
}

function dashXml(value: string | null | undefined, strokeWidth: number): string {
  if (!value || value === "none") return "";
  const nums = dasharrayNumbers(value);
  if (!nums || nums.reduce((sum, item) => sum + item, 0) <= 0) return "";
  if (strokeWidth > 0) {
    const even = nums.length % 2 === 1 ? nums.concat(nums) : nums;
    const parts: string[] = [];
    for (let index = 0; index + 1 < even.length; index += 2) {
      parts.push(`<a:ds d="${Math.round(Math.max(0, even[index]!) / strokeWidth * 100000)}" sp="${Math.round(Math.max(0, even[index + 1]!) / strokeWidth * 100000)}"/>`);
    }
    return `<a:custDash>${parts.join("")}</a:custDash>`;
  }
  return "";
}

function joinXml(value: string | null | undefined, miterlimit?: number | null): string {
  if (value === "round") return "<a:round/>";
  if (value === "bevel") return "<a:bevel/>";
  if (value === "miter") {
    const limit = miterlimit == null ? "" : ` lim="${Math.round(Math.max(1, miterlimit) * 100000)}"`;
    return `<a:miter${limit}/>`;
  }
  return "";
}

function svgLineCapToDml(value: string | null | undefined): string | null {
  if (value === "round") return "rnd";
  if (value === "square") return "sq";
  if (value === "butt") return "flat";
  return null;
}

function alphaXml(value: number | null | undefined): string {
  if (value == null || value >= 1) return "";
  return `<a:alpha val="${Math.round(clamp(value, 0, 1) * 100000)}"/>`;
}

function blipAlphaXml(value: number | null | undefined): string {
  if (value == null || value >= 1) return "";
  return `<a:alphaModFix amt="${Math.round(clamp(value, 0, 1) * 100000)}"/>`;
}

function writePptx(slideXmls: string[], svgraph: SVGraphDocument, sourceSvg: string): Uint8Array {
  const presentation = svgraph.presentation;
  const masterCount = Math.max(1, presentation.masters.length);
  const layoutCount = Math.max(1, presentation.layouts.length);
  const files: Record<string, string | Uint8Array> = {
    "[Content_Types].xml": contentTypes(slideXmls.length, masterCount, layoutCount, true, true),
    "_rels/.rels": rootRels(true, true),
    "docProps/app.xml": appProps(slideXmls.length),
    "docProps/core.xml": coreProps,
    "customXml/item1.xml": svgraphPresentationSidecar(presentation, sourceSvg),
    "ocz/causal.jsonl": buildOfficeCausalJsonl(svgraph),
    "ppt/presentation.xml": presentationXml(slideXmls.length, presentation.slide_size, masterCount),
    "ppt/_rels/presentation.xml.rels": presentationRels(slideXmls.length, masterCount),
    "ppt/theme/theme1.xml": themeXml,
  };
  for (let index = 1; index <= masterCount; index += 1) {
    const layoutIndex = Math.min(index, layoutCount);
    files[`ppt/slideMasters/slideMaster${index}.xml`] = slideMaster(presentation.text_styles);
    files[`ppt/slideMasters/_rels/slideMaster${index}.xml.rels`] = slideMasterRels(layoutIndex);
  }
  for (let index = 1; index <= layoutCount; index += 1) {
    const masterIndex = Math.min(index, masterCount);
    files[`ppt/slideLayouts/slideLayout${index}.xml`] = slideLayout;
    files[`ppt/slideLayouts/_rels/slideLayout${index}.xml.rels`] = slideLayoutRels(masterIndex);
  }
  let nextMediaIndex = 1;
  slideXmls.forEach((slide, index) => {
    const prepared = prepareSlideMedia(slide, nextMediaIndex, Math.min(index + 1, layoutCount));
    nextMediaIndex += Object.keys(prepared.media).length;
    files[`ppt/slides/slide${index + 1}.xml`] = prepared.xml;
    files[`ppt/slides/_rels/slide${index + 1}.xml.rels`] = prepared.rels;
    Object.assign(files, prepared.media);
  });
  return zipStore(files);
}

function prepareSlideMedia(slideXml: string, firstMediaIndex: number, layoutIndex = 1): PreparedSlide {
  const media: Record<string, Uint8Array> = {};
  const relationships = [slideLayoutRel(layoutIndex)];
  let nextRelId = 2;
  let nextMediaIndex = firstMediaIndex;
  const xml = slideXml.replace(/r:embed="(data:image\/(png|jpeg|jpg|gif|webp);base64,([^"]+))"/gi, (_match, _uri: string, kind: string, payload: string) => {
    const data = base64PayloadBytes(payload);
    if (!data) return _match;
    const extension = kind.toLowerCase() === "jpeg" ? "jpg" : kind.toLowerCase();
    const relId = `rId${nextRelId}`;
    const path = `ppt/media/image${nextMediaIndex}.${extension}`;
    media[path] = data;
    relationships.push(`<Relationship Id="${relId}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image${nextMediaIndex}.${extension}"/>`);
    nextRelId += 1;
    nextMediaIndex += 1;
    return `r:embed="${relId}"`;
  });
  return {
    xml,
    rels: xmlDecl(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${relationships.join("")}</Relationships>`),
    media,
  };
}

function base64Bytes(value: string): Uint8Array {
  const binary = atob(value.replace(/\s+/g, ""));
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function zipStore(files: Record<string, string | Uint8Array>): Uint8Array {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const central: Uint8Array[] = [];
  let offset = 0;
  for (const [name, content] of Object.entries(files)) {
    const nameBytes = encoder.encode(name);
    const data = typeof content === "string" ? encoder.encode(content) : content;
    const crc = crc32(data);
    const local = concat([
      u32(0x04034b50),
      u16(20),
      u16(0),
      u16(0),
      u16(0),
      u16(0),
      u32(crc),
      u32(data.length),
      u32(data.length),
      u16(nameBytes.length),
      u16(0),
      nameBytes,
      data,
    ]);
    chunks.push(local);
    central.push(
      concat([
        u32(0x02014b50),
        u16(20),
        u16(20),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(crc),
        u32(data.length),
        u32(data.length),
        u16(nameBytes.length),
        u16(0),
        u16(0),
        u16(0),
        u16(0),
        u32(0),
        u32(offset),
        nameBytes,
      ]),
    );
    offset += local.length;
  }
  const centralOffset = offset;
  const centralData = concat(central);
  const end = concat([u32(0x06054b50), u16(0), u16(0), u16(central.length), u16(central.length), u32(centralData.length), u32(centralOffset), u16(0)]);
  return concat([...chunks, centralData, end]);
}

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) {
    crc = (crc >>> 8) ^ crcTable[(crc ^ byte) & 0xff]!;
  }
  return (crc ^ 0xffffffff) >>> 0;
}

const crcTable = Array.from({ length: 256 }, (_, index) => {
  let c = index;
  for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function u16(value: number): Uint8Array {
  return new Uint8Array([value & 0xff, (value >>> 8) & 0xff]);
}

function u32(value: number): Uint8Array {
  return new Uint8Array([value & 0xff, (value >>> 8) & 0xff, (value >>> 16) & 0xff, (value >>> 24) & 0xff]);
}

function concat(chunks: Uint8Array[]): Uint8Array {
  const output = new Uint8Array(chunks.reduce((total, chunk) => total + chunk.length, 0));
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}

function render(): void {
  try {
    const text = source.value;
    if (state.assistantProposalSource && state.assistantProposalSource !== text) {
      state.assistantProposal = null;
      state.assistantProposalSource = "";
      state.assistantRawOutput = "";
    }
    state.svgraph = buildSVGraph(text);
    state.presentation = state.svgraph.presentation;
    preview.innerHTML = text;
  } catch (error) {
    preview.innerHTML = "";
    state.svgraph = null;
    state.presentation = null;
    panel.innerHTML = `<div class="notice">${escapeHtml(error instanceof Error ? error.message : String(error))}</div>`;
    return;
  }
  renderPanel();
}

function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] || char);
}

function renderPanel(): void {
  if (!state.svgraph || !state.presentation) return;
  const nodes = flatten(state.svgraph.root);
  const semantic = nodes.filter((node) => Object.keys(node.data).length > 0).length;
  const deps = state.svgraph.dependencies.length;
  const templatesCount = state.presentation.masters.length + state.presentation.layouts.length + state.presentation.text_styles.length;
  const coverage = state.svgraph.coverage;
  const warningCount = coverageCount(coverage.unsupported_elements) + coverageCount(coverage.unsupported_attributes) + coverageCount(coverage.unsupported_path_commands);
  if (state.tab === "summary") {
    panel.innerHTML = `
      <div class="metrics">
        <div class="metric"><strong>${nodes.length}</strong><span>SVGraph nodes</span></div>
        <div class="metric"><strong>${state.presentation.slides.length}</strong><span>presentation slides</span></div>
        <div class="metric"><strong>${Math.round(coverage.estimated_element_coverage * 100)}%</strong><span>coverage</span></div>
        <div class="metric"><strong>${warningCount}</strong><span>warnings</span></div>
        <div class="metric"><strong>${semantic}</strong><span>semantic nodes</span></div>
        <div class="metric"><strong>${templatesCount}</strong><span>templates</span></div>
        <div class="metric"><strong>${deps}</strong><span>dependencies</span></div>
        <div class="metric"><strong>${state.presentation.guides.length + state.presentation.rulers.length}</strong><span>guides/rulers</span></div>
      </div>
      ${warningCount ? `<div class="notice">${escapeHtml(coverageSummary(coverage))}</div>` : ""}
      <div class="notice">${escapeHtml(state.storageStatus)}</div>
      <div class="list">
        ${nodes.slice(0, 12).map((node) => `<div class="item"><div class="item-title">${escapeHtml(node.node_id)} · ${escapeHtml(node.tag)}</div><div class="item-meta">${escapeHtml(JSON.stringify(node.data))}</div></div>`).join("")}
      </div>`;
  } else if (state.tab === "slides") {
    panel.innerHTML = `
      <div class="list">
        ${state.presentation.slides.map((slide) => `<div class="item"><div class="item-title">${escapeHtml(slide.slide_id)}${slide.title ? ` · ${escapeHtml(slide.title)}` : ""}</div><div class="item-meta">${escapeHtml(slide.node_id)} · viewBox ${slide.view_box.join(" ")}</div></div>`).join("")}
      </div>
      <div class="list" style="margin-top:12px">
        ${state.presentation.parts.map((part) => `<div class="item"><div class="item-title">${escapeHtml(part.kind)} · ${escapeHtml(part.part_name)}</div><div class="item-meta">${escapeHtml(part.content_type)}${part.source_node_id ? ` · ${escapeHtml(part.source_node_id)}` : ""}</div></div>`).join("")}
      </div>`;
  } else if (state.tab === "assistant") {
    const proposal = activeAssistantProposal(state.svgraph, state.presentation);
    const validation = validateAssistantPatch(proposal, state.svgraph);
    const diff = assistantPatchDiff(proposal, state.svgraph);
    const proposalSource = state.assistantProposal ? "local LLM" : "deterministic";
    panel.innerHTML = `
      <div class="notice">Local Web LLM suggestions run in a browser worker and only produce reviewable SVGraph patch proposals. Conversion remains deterministic in this page.</div>
      <div class="status"><span class="dot ${state.webgpu ? "ok" : ""}"></span>${state.webgpu ? "WebGPU available" : "WebGPU unavailable or blocked"}</div>
      <div class="status" style="margin-top:8px">${escapeHtml(state.assistantStatus)} · proposal source: ${escapeHtml(proposalSource)}</div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">
        <select id="assistantBackendPolicy" aria-label="Assistant backend policy">
          <option value="webgpu" ${state.assistantBackendPolicy === "webgpu" ? "selected" : ""}>WebGPU</option>
          <option value="wasm" ${state.assistantBackendPolicy === "wasm" ? "selected" : ""}>WASM</option>
          <option value="disabled" ${state.assistantBackendPolicy === "disabled" ? "selected" : ""}>Disabled</option>
        </select>
        <button class="btn" id="runAssistantLlmBtn" type="button">Suggest With Local LLM</button>
        <button class="btn" id="resetAssistantProposalBtn" type="button" ${state.assistantProposal ? "" : "disabled"}>Use Deterministic</button>
      </div>
      <div class="list" style="margin-top:12px">
        ${diff.length ? diff.map((row) => `<div class="item"><div class="item-title">${escapeHtml(row.status)} · ${escapeHtml(row.op)} · ${escapeHtml(row.field)}</div><div class="item-meta">${escapeHtml(row.node_id)} · ${escapeHtml(JSON.stringify(row.before))} -> ${escapeHtml(JSON.stringify(row.after))}</div></div>`).join("") : '<div class="item"><div class="item-title">unchanged</div><div class="item-meta">No pending SVGraph patch changes.</div></div>'}
      </div>
      <button class="btn primary" id="applyAssistantPatchBtn" type="button" style="margin-top:12px" ${validation.status === "accepted" && diff.some((row) => row.status === "pending") ? "" : "disabled"}>Apply Patch</button>
      <pre style="margin-top:12px">${escapeHtml(JSON.stringify({
        backendPolicy: state.assistantBackendPolicy,
        allowedOps: assistantAllowedOps,
        model: assistantModelId,
        prompt: state.svgraph && state.presentation ? JSON.parse(buildSVGraphAssistantPrompt(state.svgraph, state.presentation)) : null,
        rawLlmOutput: state.assistantRawOutput,
        patchValidation: validation,
        patchDiff: diff,
        patchProposal: proposal,
        coverage: state.svgraph.coverage
      }, null, 2))}</pre>`;
    const applyButton = document.getElementById("applyAssistantPatchBtn") as HTMLButtonElement | null;
    const policySelect = document.getElementById("assistantBackendPolicy") as HTMLSelectElement | null;
    const runButton = document.getElementById("runAssistantLlmBtn") as HTMLButtonElement | null;
    const resetButton = document.getElementById("resetAssistantProposalBtn") as HTMLButtonElement | null;
    policySelect?.addEventListener("change", () => {
      const value = policySelect.value;
      state.assistantBackendPolicy = value === "wasm" || value === "disabled" ? value : "webgpu";
      renderPanel();
    });
    runButton?.addEventListener("click", () => {
      void requestAssistantPatch(state.assistantBackendPolicy);
    });
    resetButton?.addEventListener("click", () => {
      state.assistantProposal = null;
      state.assistantProposalSource = "";
      state.assistantRawOutput = "";
      state.assistantStatus = "Deterministic proposal is active";
      renderPanel();
    });
    applyButton?.addEventListener("click", () => {
      if (!state.svgraph) return;
      setSourceValue(applyAssistantPatch(source.value, proposal, state.svgraph));
    });
  } else {
    panel.innerHTML = `<pre>${escapeHtml(JSON.stringify(state.svgraph, null, 2))}</pre>`;
  }
}

function coverageCount(counts: Record<string, number>): number {
  return Object.values(counts).reduce((total, value) => total + value, 0);
}

function coverageSummary(coverage: SvgCoverage): string {
  const parts = [
    coverageList("elements", coverage.unsupported_elements),
    coverageList("attributes", coverage.unsupported_attributes),
    coverageList("path", coverage.unsupported_path_commands),
  ].filter(Boolean);
  return parts.join(" · ");
}

function coverageList(label: string, counts: Record<string, number>): string {
  const entries = Object.entries(counts);
  if (!entries.length) return "";
  return `${label}: ${entries.map(([key, value]) => `${key} ${value}`).join(", ")}`;
}

function downloadText(name: string, value: string): void {
  downloadBlob(name, new Blob([value], { type: "application/json;charset=utf-8" }));
}

function downloadBlob(name: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

function sourceFromOpenedFile(text: string): string {
  if (text.trimStart().startsWith("<")) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(text, "application/xml");
    const error = doc.querySelector("parsererror");
    if (error) throw new Error((error.textContent || "").trim());
    return localName(doc.documentElement) === "svg" ? text : drawingMlToSvg(text);
  }
  const payload = JSON.parse(text) as JsonValue;
  const obj = asObject(payload);
  if (obj.kind === "svgraph-sidecar" && typeof obj.source_svg === "string") return obj.source_svg;
  throw new Error("Opened JSON does not contain svgraph-sidecar source_svg");
}

async function checkWebGpu(): Promise<void> {
  const nav = navigator as Navigator & { gpu?: { requestAdapter: () => Promise<unknown> } };
  if (!nav.gpu) {
    state.webgpu = false;
    renderPanel();
    return;
  }
  try {
    state.webgpu = Boolean(await nav.gpu.requestAdapter());
  } catch (_) {
    state.webgpu = false;
  }
  renderPanel();
}

export function initSVGraphEditor(): void {
  source = mustElement<HTMLTextAreaElement>("source");
  preview = mustElement<HTMLElement>("preview");
  panel = mustElement<HTMLElement>("panel");
  fileInput = mustElement<HTMLInputElement>("fileInput");
  undoButton = mustElement<HTMLButtonElement>("undoBtn");
  redoButton = mustElement<HTMLButtonElement>("redoBtn");
  clearSavedButton = mustElement<HTMLButtonElement>("clearSavedBtn");

  document.querySelectorAll<HTMLButtonElement>(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      state.tab = tab.dataset.tab || "summary";
      document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === tab));
      renderPanel();
    });
  });

  mustElement<HTMLButtonElement>("openBtn").addEventListener("click", () => fileInput.click());
  mustElement<HTMLButtonElement>("sampleBtn").addEventListener("click", () => {
    setSourceValue(sampleSvg);
  });
  undoButton.addEventListener("click", undoSourceEdit);
  redoButton.addEventListener("click", redoSourceEdit);
  clearSavedButton.addEventListener("click", () => {
    void clearSavedSourceDocumentWithStatus();
  });
  mustElement<HTMLButtonElement>("downloadSvgBtn").addEventListener("click", () => {
    downloadBlob("svgraph-source.svg", new Blob([source.value], { type: "image/svg+xml;charset=utf-8" }));
  });
  mustElement<HTMLButtonElement>("downloadSVGraphBtn").addEventListener("click", () => {
    if (state.svgraph) downloadText("svgraph.json", JSON.stringify(state.svgraph, null, 2));
  });
  mustElement<HTMLButtonElement>("downloadSidecarBtn").addEventListener("click", () => {
    if (state.svgraph) downloadText("svgraph-sidecar.json", JSON.stringify(buildSVGraphSidecar(state.svgraph, source.value), null, 2));
  });
  mustElement<HTMLButtonElement>("downloadDrawingMlBtn").addEventListener("click", () => {
    downloadBlob("svgraph-drawingml.xml", new Blob([svgToDrawingMl(source.value)], { type: "application/xml;charset=utf-8" }));
  });
  mustElement<HTMLButtonElement>("downloadPresentationBtn").addEventListener("click", () => {
    if (state.presentation) downloadText("svgraph-presentation.json", JSON.stringify(state.presentation, null, 2));
  });
  mustElement<HTMLButtonElement>("downloadPptxBtn").addEventListener("click", () => {
    const bytes = svgToPptx(source.value);
    const data = new Uint8Array(bytes.byteLength);
    data.set(bytes);
    downloadBlob("svgraph-web.pptx", new Blob([data], { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" }));
  });
  fileInput.addEventListener("change", async () => {
    const file = fileInput.files?.[0];
    if (!file) return;
    try {
      setSourceValue(sourceFromOpenedFile(await file.text()));
      setStorageStatus(`Opened ${file.name}`);
    } catch (error) {
      setStorageStatus(`Open failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      fileInput.value = "";
    }
  });
  source.addEventListener("input", recordManualSourceEdit);

  setSourceValue(sampleSvg, { record: false, persist: false });
  void loadSourceDocument().then((saved) => {
    if (saved) {
      setSourceValue(saved, { record: false, persist: false });
      setStorageStatus("Restored active SVG source from IndexedDB");
    }
  }).catch((error) => {
    setStorageStatus(`Storage restore failed: ${error instanceof Error ? error.message : String(error)}`);
  });
  void checkWebGpu();
}

if (typeof document !== "undefined" && document.getElementById("source")) initSVGraphEditor();

function asObject(value: JsonValue | undefined): Record<string, JsonValue> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value;
}

function num(element: Element, name: string, fallback = 0): number {
  const value = Number(element.getAttribute(name));
  return Number.isFinite(value) ? value : fallback;
}

function geom(element: Element, name: string, axis: "x" | "y" | "diag", viewport: Viewport, fallback = 0): number {
  const value = element.getAttribute(name);
  return parseCssLength(value, percentageBasis(axis, viewport), fallback);
}

function optionalGeom(element: Element, name: string, axis: "x" | "y" | "diag", viewport: Viewport): number | null {
  if (!element.hasAttribute(name)) return null;
  const parsed = parseCssLength(element.getAttribute(name), percentageBasis(axis, viewport), Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function firstOptionalGeom(element: Element, name: string, axis: "x" | "y" | "diag", viewport: Viewport): number | null {
  const value = element.getAttribute(name);
  if (value == null) return null;
  const first = value.trim().split(/[\s,]+/, 1)[0] || "";
  const parsed = parseCssLength(first, percentageBasis(axis, viewport), Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function cascadedGeomValue(element: Element, declarations: Record<string, string>, name: string): string | null {
  return declarations[name] ?? element.getAttribute(name);
}

function cascadedGeom(element: Element, declarations: Record<string, string>, name: string, axis: "x" | "y" | "diag", viewport: Viewport, fallback = 0): number {
  const value = cascadedGeomValue(element, declarations, name);
  return parseCssLength(value, percentageBasis(axis, viewport), fallback);
}

function optionalCascadedGeom(element: Element, declarations: Record<string, string>, name: string, axis: "x" | "y" | "diag", viewport: Viewport): number | null {
  const value = cascadedGeomValue(element, declarations, name);
  if (value == null) return null;
  const parsed = parseCssLength(value, percentageBasis(axis, viewport), Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function optionalNonnegativeCascadedGeom(element: Element, declarations: Record<string, string>, name: string, axis: "x" | "y" | "diag", viewport: Viewport): number | null {
  const parsed = optionalCascadedGeom(element, declarations, name, axis, viewport);
  return parsed != null && parsed >= 0 ? parsed : null;
}

function rectRadius(element: Element, declarations: Record<string, string>, viewport: Viewport): number {
  const rx = optionalNonnegativeCascadedGeom(element, declarations, "rx", "x", viewport);
  const ry = optionalNonnegativeCascadedGeom(element, declarations, "ry", "y", viewport);
  if (rx == null && ry == null) return 0;
  if (rx == null) return ry ?? 0;
  if (ry == null) return rx;
  return Math.max(rx, ry);
}

function firstOptionalCascadedGeom(element: Element, declarations: Record<string, string>, name: string, axis: "x" | "y" | "diag", viewport: Viewport): number | null {
  const value = cascadedGeomValue(element, declarations, name);
  if (value == null) return null;
  const first = value.trim().split(/[\s,]+/, 1)[0] || "";
  const parsed = parseCssLength(first, percentageBasis(axis, viewport), Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function bboxCascadedGeom(element: Element, declarations: Record<string, string>, name: string, fallback = 0): number {
  const parsed = parseCssLength(cascadedGeomValue(element, declarations, name), 1, Number.NaN);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function percentageBasis(axis: "x" | "y" | "diag", viewport: Viewport): number {
  if (axis === "x") return viewport.width;
  if (axis === "y") return viewport.height;
  return Math.hypot(viewport.width, viewport.height) / Math.SQRT2;
}

function svgViewport(root: Element): Viewport {
  const box = viewBoxValues(root);
  if (box && box.width > 0 && box.height > 0) {
    return { width: box.width, height: box.height };
  }
  const width = parseCssLength(root.getAttribute("width"), Number.NaN, 0);
  const height = parseCssLength(root.getAttribute("height"), Number.NaN, 0);
  return { width: width > 0 ? width : defaultViewport().width, height: height > 0 ? height : defaultViewport().height };
}

function defaultViewport(): Viewport {
  return { width: 1280, height: 720 };
}

function renderedSvgViewport(element: Element, parentViewport: Viewport = defaultViewport(), css: CssRule[] = [], inheritedStyle: SvgStyle = {}): Viewport {
  const box = viewBoxValues(element);
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
  const width = optionalCascadedGeom(element, declarations, "width", "x", parentViewport) ?? box?.width ?? defaultViewport().width;
  const height = optionalCascadedGeom(element, declarations, "height", "y", parentViewport) ?? box?.height ?? defaultViewport().height;
  return { width: width > 0 ? width : (box?.width ?? defaultViewport().width), height: height > 0 ? height : (box?.height ?? defaultViewport().height) };
}

function viewBoxValues(element: Element): { minX: number; minY: number; width: number; height: number } | null {
  const values = element.getAttribute("viewBox")?.match(/[+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?/gi)?.map(Number) ?? [];
  if (values.length < 4) return null;
  const [minX, minY, width, height] = values as [number, number, number, number];
  return Number.isFinite(minX) && Number.isFinite(minY) && Number.isFinite(width) && Number.isFinite(height) && width !== 0 && height !== 0
    ? { minX, minY, width, height }
    : null;
}

function useViewport(ref: Element, useElement: Element, viewport: Viewport, css: CssRule[] = [], inheritedStyle: SvgStyle = {}): Viewport {
  const refBox = viewBoxValues(ref);
  const refDeclarations = resolvedCascadedDeclarations(ref, css, inheritedStyle);
  const useDeclarations = resolvedCascadedDeclarations(useElement, css, inheritedStyle);
  const widthFallback = refBox?.width ?? cascadedGeom(ref, refDeclarations, "width", "x", viewport);
  const heightFallback = refBox?.height ?? cascadedGeom(ref, refDeclarations, "height", "y", viewport);
  return {
    width: optionalCascadedGeom(useElement, useDeclarations, "width", "x", viewport) ?? widthFallback,
    height: optionalCascadedGeom(useElement, useDeclarations, "height", "y", viewport) ?? heightFallback,
  };
}

function viewBoxMatrix(element: Element, viewport: Viewport, preserveAspectRatioOverride: string | null = null): Matrix {
  const box = viewBoxValues(element);
  if (!box || viewport.width === 0 || viewport.height === 0) return [1, 0, 0, 1, 0, 0];
  const sx = viewport.width / box.width;
  const sy = viewport.height / box.height;
  const [align, meetOrSlice] = parsePreserveAspectRatio(preserveAspectRatioOverride ?? element.getAttribute("preserveAspectRatio"));
  if (align === "none") return multiply([sx, 0, 0, sy, 0, 0], [1, 0, 0, 1, -box.minX, -box.minY]);
  const scale = meetOrSlice === "slice" ? Math.max(sx, sy) : Math.min(sx, sy);
  const extraX = viewport.width - box.width * scale;
  const extraY = viewport.height - box.height * scale;
  const offsetX = aspectAlignmentOffset(align.slice(1, 4), extraX);
  const offsetY = aspectAlignmentOffset(align.slice(5, 8), extraY);
  return multiply([1, 0, 0, 1, offsetX, offsetY], multiply([scale, 0, 0, scale, 0, 0], [1, 0, 0, 1, -box.minX, -box.minY]));
}

function parsePreserveAspectRatio(value: string | null): [string, "meet" | "slice"] {
  let parts = (value || "xMidYMid meet").trim().split(/\s+/).filter(Boolean);
  if (parts[0]?.toLowerCase() === "defer") parts = parts.slice(1);
  const alignToken = parts[0] || "xMidYMid";
  if (alignToken.toLowerCase() === "none") return ["none", "meet"];
  const alignments = new Map<string, string>();
  for (const x of ["Min", "Mid", "Max"]) {
    for (const y of ["Min", "Mid", "Max"]) alignments.set(`x${x}Y${y}`.toLowerCase(), `x${x}Y${y}`);
  }
  const align = alignments.get(alignToken.toLowerCase()) ?? "xMidYMid";
  const meetOrSlice = parts[1]?.toLowerCase() === "slice" ? "slice" : "meet";
  return [align, meetOrSlice];
}

function aspectAlignmentOffset(part: string, extra: number): number {
  if (part === "Mid") return extra / 2;
  if (part === "Max") return extra;
  return 0;
}

function computedStyle(element: Element, inherited: SvgStyle, css: CssRule[] = [], refs: Map<string, Element> = new Map(), viewport: Viewport = defaultViewport()): SvgStyle {
  const declarations = resolvedCascadedDeclarations(element, css, inherited);
  const value = (name: string): string | null => declarations[name] ?? null;
  const tag = localName(element);
  const next: SvgStyle = { ...inherited, customProperties: customPropertiesFromDeclarations(declarations, inherited) };
  const color = value("color");
  const fill = value("fill");
  const fillRule = value("fill-rule");
  const stroke = value("stroke");
  const display = value("display");
  const visibility = value("visibility");
  const opacity = value("opacity");
  const fillOpacity = value("fill-opacity");
  const strokeOpacity = value("stroke-opacity");
  const strokeWidth = value("stroke-width");
  const strokeLineCap = value("stroke-linecap");
  const strokeLineJoin = value("stroke-linejoin");
  const strokeMiterlimit = value("stroke-miterlimit");
  const strokeDasharray = value("stroke-dasharray");
  const strokeDashoffset = value("stroke-dashoffset");
  const fontSize = value("font-size");
  const fontFamily = value("font-family");
  const fontWeight = value("font-weight");
  const fontStyle = value("font-style");
  const fontVariant = value("font-variant");
  const textDecoration = [value("text-decoration-line") ?? value("text-decoration"), value("text-decoration-style")].filter(Boolean).join(" ") || null;
  const textDecorationColor = value("text-decoration-color");
  const textDecorationThickness = value("text-decoration-thickness");
  const textTransform = value("text-transform");
  const textAnchor = value("text-anchor");
  const textBaseline = value("dominant-baseline") ?? value("alignment-baseline");
  const baselineShift = value("baseline-shift");
  const letterSpacing = value("letter-spacing");
  const wordSpacing = value("word-spacing");
  const textLength = declarations.textLength ?? null;
  const lengthAdjust = declarations.lengthAdjust ?? null;
  const rotate = value("rotate");
  const direction = value("direction");
  const pathLength = declarations.pathLength ?? null;
  const clipPath = value("clip-path");
  const overflow = value("overflow");
  const transform = value("transform");
  const transformOrigin = value("transform-origin");
  const vectorEffect = value("vector-effect");
  const isolation = value("isolation");
  const mixBlendMode = value("mix-blend-mode");
  const marker = value("marker");
  const markerStart = value("marker-start");
  const markerMid = value("marker-mid");
  const markerEnd = value("marker-end");
  delete next.display;
  delete next.transform;
  delete next.transformOrigin;
  if (display != null) next.display = normalizeDisplay(display);
  if (visibility != null) next.visibility = normalizeVisibility(visibility);
  if (color != null) {
    next.color = parseCssColor(color, next);
    next.colorAlpha = cssColorAlpha(color);
  }
  const opacityAlpha = parseAlpha(opacity);
  if (opacityAlpha != null) next.imageAlpha = combinedAlpha(opacityAlpha, next.imageAlpha);
  const fillPaint = fill != null ? normalizePaintValue(fill, refs, next, css) : null;
  const strokePaint = stroke != null ? normalizePaintValue(stroke, refs, next, css) : null;
  if (fillPaint) {
    next.fill = fillPaint.color;
    next.fillAlpha = combinedAlpha(opacityAlpha, parseAlpha(fillOpacity), fillPaint.alpha);
  } else if (fill != null) {
    next.fill = null;
    next.fillAlpha = null;
  } else if (opacityAlpha != null || fillOpacity != null) {
    next.fillAlpha = combinedAlpha(opacityAlpha, parseAlpha(fillOpacity), next.fillAlpha);
  }
  if (fillRule != null) next.fillRule = fillRule.trim().toLowerCase();
  if (strokePaint) {
    next.stroke = strokePaint.color;
    next.strokeAlpha = combinedAlpha(opacityAlpha, parseAlpha(strokeOpacity), strokePaint.alpha);
  } else if (stroke != null) {
    next.stroke = null;
    next.strokeAlpha = null;
  } else if (opacityAlpha != null || strokeOpacity != null) {
    next.strokeAlpha = combinedAlpha(opacityAlpha, parseAlpha(strokeOpacity), next.strokeAlpha);
  }
  if (strokeWidth != null) next.strokeWidth = normalizeStrokeWidth(strokeWidth, next.fontSize ?? rootFontSize, next.strokeWidth ?? 1);
  if (strokeLineCap != null) {
    next.strokeLineCap = normalizeStrokeLineCap(strokeLineCap);
    next.strokeLineCapSource = strokeLineCap;
  }
  if (strokeLineJoin != null) {
    next.strokeLineJoin = normalizeStrokeLineJoin(strokeLineJoin);
    next.strokeLineJoinSource = strokeLineJoin;
  }
  if (strokeMiterlimit != null) next.strokeMiterlimit = normalizeStrokeMiterlimit(strokeMiterlimit);
  if (next.strokeLineJoin === "miter" && next.strokeMiterlimit == null) next.strokeMiterlimit = 4;
  const dashBasis = percentageBasis("diag", viewport);
  if (strokeDashoffset != null) next.strokeDashoffset = parseCssLength(strokeDashoffset, dashBasis, next.strokeDashoffset ?? 0);
  if (strokeDasharray != null) next.strokeDasharray = normalizeStrokeDasharray(strokeDasharray, dashBasis);
  if ((strokeDasharray != null || strokeDashoffset != null) && next.strokeDasharray && next.strokeDashoffset) {
    next.strokeDasharray = normalizeStrokeDasharrayWithOffset(next.strokeDasharray, next.strokeDashoffset, dashBasis) ?? next.strokeDasharray;
  }
  if (fontSize != null) next.fontSize = parseFontSize(fontSize, next.fontSize ?? 18);
  if (fontFamily != null) next.fontFamily = normalizeFontFamily(fontFamily);
  if (fontWeight != null) next.fontWeight = fontWeight;
  if (fontStyle != null) next.fontStyle = fontStyle;
  if (fontVariant != null) next.fontVariant = normalizeFontVariant(fontVariant);
  if (textDecoration != null) next.textDecoration = textDecoration;
  applyTextDecorationDetails(next, textDecoration, textDecorationColor, textDecorationThickness, percentageBasis("diag", viewport));
  if (textTransform != null) next.textTransform = normalizeTextTransform(textTransform);
  if (textAnchor != null) next.textAnchor = normalizeTextAnchor(textAnchor);
  if (textBaseline != null) next.textBaseline = normalizeTextBaseline(textBaseline);
  if (baselineShift != null) next.baselineShift = normalizeBaselineShift(baselineShift);
  if (letterSpacing != null) next.letterSpacing = normalizeSpacingLength(letterSpacing, next.fontSize ?? rootFontSize);
  if (wordSpacing != null) next.wordSpacing = normalizeSpacingLength(wordSpacing, next.fontSize ?? rootFontSize);
  if (lengthAdjust != null) next.lengthAdjust = normalizeLengthAdjust(lengthAdjust);
  if (textLength != null) next.textLength = textLengthIsSupported(element, tag, textLength, next, lengthAdjust) ? parseCssLength(textLength, next.fontSize ?? rootFontSize, 0) : null;
  if (rotate != null) next.rotate = singleTextRotation(rotate, element.textContent || null);
  if (direction != null) next.direction = normalizeTextDirection(direction);
  if (pathLength != null) next.pathLength = normalizePathLength(pathLength);
  if (clipPath != null) next.clipPath = clipPath.trim();
  if (overflow != null) next.overflow = normalizeOverflow(overflow);
  if (transform != null) next.transform = transform.trim();
  if (transformOrigin != null) next.transformOrigin = transformOrigin.trim();
  if (vectorEffect != null) next.vectorEffect = normalizeVectorEffect(vectorEffect);
  if (isolation != null) next.isolation = isolation.trim().toLowerCase();
  if (mixBlendMode != null) next.mixBlendMode = mixBlendMode.trim().toLowerCase();
  if (marker != null) {
    const enabled = normalizeMarkerReference(marker, refs);
    next.markerStart = enabled;
    next.markerMid = enabled;
    next.markerMidSource = enabled ? "marker" : null;
    next.markerEnd = enabled;
  }
  if (markerStart != null) next.markerStart = normalizeMarkerReference(markerStart, refs);
  if (markerMid != null) {
    next.markerMid = normalizeMarkerReference(markerMid, refs);
    next.markerMidSource = next.markerMid ? "marker-mid" : null;
  }
  if (markerEnd != null) next.markerEnd = normalizeMarkerReference(markerEnd, refs);
  return next;
}

function collectCss(root: Element): CssRule[] {
  const rules: CssRule[] = [];
  let order = 0;
  for (const style of Array.from(root.querySelectorAll("style"))) {
    const text = (style.textContent || "").replace(/\/\*[\s\S]*?\*\//g, "");
    order = collectCssRules(text, rules, order);
  }
  return rules;
}

function collectCssRules(text: string, rules: CssRule[], order: number): number {
  for (const [selectorText, body] of cssRuleBlocks(text)) {
    const selector = selectorText.trim();
    if (selector.toLowerCase().startsWith("@media")) {
      if (mediaQueryApplies(selector.slice(6).trim())) order = collectCssRules(body, rules, order);
      continue;
    }
    if (!selector || selector.startsWith("@")) continue;
    for (const item of selectorList(selector)) {
      rules.push({ selector: item, declarations: parseStyleDeclarations(body), specificity: selectorSpecificity(item), order });
      order += 1;
    }
  }
  return order;
}

function cssRuleBlocks(text: string): [string, string][] {
  const blocks: [string, string][] = [];
  let index = 0;
  while (index < text.length) {
    const start = text.indexOf("{", index);
    if (start < 0) break;
    const selector = text.slice(index, start).trim();
    let depth = 1;
    let quote: string | null = null;
    let end = start + 1;
    while (end < text.length) {
      const char = text[end];
      if (quote) {
        if (char === quote) quote = null;
      } else if (char === "'" || char === "\"") {
        quote = char;
      } else if (char === "{") {
        depth += 1;
      } else if (char === "}") {
        depth -= 1;
        if (depth === 0) break;
      }
      end += 1;
    }
    if (depth === 0 && selector) blocks.push([selector, text.slice(start + 1, end)]);
    index = end + 1;
  }
  return blocks;
}

function mediaQueryApplies(query: string): boolean {
  const normalized = query.trim().toLowerCase().split(/\s+/).join(" ");
  if (!normalized) return true;
  return normalized.split(",").some((item) => singleMediaQueryApplies(item.trim()));
}

function singleMediaQueryApplies(query: string): boolean {
  let normalized = query;
  if (normalized.startsWith("only ")) normalized = normalized.slice(5).trim();
  if (normalized.startsWith("not ")) return !singleMediaQueryApplies(normalized.slice(4).trim());
  return normalized === "all" || normalized === "screen" || normalized.startsWith("all and ") || normalized.startsWith("screen and ");
}

function collectRefs(root: Element): Map<string, Element> {
  const refs = new Map<string, Element>();
  const walk = (element: Element) => {
    const id = element.getAttribute("id");
    if (id) refs.set(id, element);
    for (const child of Array.from(element.children)) walk(child);
  };
  walk(root);
  return refs;
}

function matchingCssDeclarations(element: Element, css: CssRule[]): Record<string, string> {
  return cascadedDeclarations(element, css, {}, false);
}

function resolvedCascadedDeclarations(element: Element, css: CssRule[], inherited: SvgStyle, aliases: Record<string, string> = {}, includePresentation = true): Record<string, string> {
  const declarations = cascadedDeclarations(element, css, aliases, includePresentation);
  const customProperties = customPropertiesFromDeclarations(declarations, inherited);
  const resolved: Record<string, string> = {};
  for (const [name, value] of Object.entries(declarations)) {
    if (name.startsWith("--")) {
      resolved[name] = resolveCssVars(value, customProperties);
      continue;
    }
    const normalized = value.trim().toLowerCase();
    if (normalized === "initial") {
      const initialValue = cssInitialValue(name);
      if (initialValue != null) resolved[name] = initialValue;
      continue;
    }
    if (normalized === "inherit" || normalized === "unset") {
      const inheritedValue = cssValueFromStyle(inherited, name);
      const fallback = normalized === "unset" ? cssInitialValue(name) : null;
      if (inheritedValue != null) resolved[name] = inheritedValue;
      else if (fallback != null) resolved[name] = fallback;
      continue;
    }
    resolved[name] = resolveCssVars(value, customProperties);
  }
  return resolved;
}

function cssInitialValue(name: string): string | null {
  const values: Record<string, string> = {
    color: "#000000",
    direction: "ltr",
    display: "inline",
    fill: "#000000",
    "fill-opacity": "1",
    "font-family": "Aptos",
    "font-size": String(rootFontSize),
    "font-style": "normal",
    "font-variant": "normal",
    "font-weight": "400",
    "letter-spacing": "0",
    opacity: "1",
    stroke: "none",
    "stroke-dasharray": "none",
    "stroke-dashoffset": "0",
    "stroke-linecap": "butt",
    "stroke-linejoin": "miter",
    "stroke-miterlimit": "4",
    "stroke-opacity": "1",
    "stroke-width": "1",
    "text-anchor": "start",
    "text-decoration": "none",
    "text-decoration-color": "currentColor",
    "text-decoration-line": "none",
    "text-decoration-style": "solid",
    "text-decoration-thickness": "auto",
    "text-transform": "none",
    visibility: "visible",
    "word-spacing": "0",
  };
  return values[name] ?? null;
}

function customPropertiesFromDeclarations(declarations: Record<string, string>, inherited: SvgStyle): Record<string, string> {
  const custom = { ...(inherited.customProperties ?? {}) };
  for (const [name, value] of Object.entries(declarations)) {
    if (name.startsWith("--")) custom[name] = resolveCssVars(value, custom);
  }
  return custom;
}

function resolveCssVars(value: string, customProperties: Record<string, string>): string {
  let resolved = value;
  for (let depth = 0; depth < 8 && resolved.includes("var("); depth += 1) {
    const next = resolveOneCssVar(resolved, customProperties);
    if (next === resolved) break;
    resolved = next;
  }
  return resolved;
}

function resolveOneCssVar(value: string, customProperties: Record<string, string>): string {
  const start = value.indexOf("var(");
  if (start < 0) return value;
  let depth = 1;
  let cursor = start + 4;
  while (cursor < value.length && depth > 0) {
    if (value[cursor] === "(") depth += 1;
    if (value[cursor] === ")") depth -= 1;
    cursor += 1;
  }
  if (depth !== 0) return value;
  const body = value.slice(start + 4, cursor - 1);
  const [name, fallback] = splitCssVarBody(body);
  const replacement = customProperties[name.trim()] ?? fallback?.trim() ?? `var(${body})`;
  return `${value.slice(0, start)}${replacement}${value.slice(cursor)}`;
}

function splitCssVarBody(body: string): [string, string | null] {
  const parts = splitCssTopLevel(body, ",");
  const name = parts.shift()?.trim() || "";
  return [name, parts.length ? parts.join(",").trim() : null];
}

function cssValueFromStyle(style: SvgStyle, name: string): string | null {
  if (name.startsWith("--")) return style.customProperties?.[name] ?? null;
  switch (name) {
    case "fill":
    case "background":
    case "background-color":
      return style.fill ?? null;
    case "fill-rule":
      return style.fillRule ?? null;
    case "stroke":
    case "border-color":
      return style.stroke ?? null;
    case "color":
      return style.color ?? null;
    case "display":
      return style.display ?? null;
    case "visibility":
      return style.visibility ?? null;
    case "stroke-width":
    case "border-width":
      return style.strokeWidth == null ? null : String(style.strokeWidth);
    case "stroke-linecap":
      return style.strokeLineCapSource ?? style.strokeLineCap ?? null;
    case "stroke-linejoin":
      return style.strokeLineJoinSource ?? style.strokeLineJoin ?? null;
    case "stroke-miterlimit":
      return style.strokeMiterlimit == null ? null : String(style.strokeMiterlimit);
    case "stroke-dasharray":
      return style.strokeDasharray ?? null;
    case "stroke-dashoffset":
      return style.strokeDashoffset == null ? null : String(style.strokeDashoffset);
    case "font-size":
      return style.fontSize == null ? null : String(style.fontSize);
    case "font-family":
      return style.fontFamily ?? null;
    case "font-weight":
      return style.fontWeight ?? null;
    case "font-style":
      return style.fontStyle ?? null;
    case "font-variant":
      return style.fontVariant ?? null;
    case "text-decoration":
    case "text-decoration-line":
      return style.textDecoration ?? null;
    case "text-decoration-style":
      return underlineStyle(style);
    case "text-decoration-color":
      return style.textDecorationColor ?? null;
    case "text-decoration-thickness":
      return style.textDecorationThickness == null ? null : String(style.textDecorationThickness);
    case "text-transform":
      return style.textTransform ?? null;
    case "text-anchor":
    case "text-align":
      return style.textAnchor ?? style.tableCellTextAlign ?? null;
    case "dominant-baseline":
    case "alignment-baseline":
      return style.textBaseline ?? null;
    case "baseline-shift":
      return style.baselineShift ?? null;
    case "letter-spacing":
      return style.letterSpacing == null ? null : String(style.letterSpacing);
    case "word-spacing":
      return style.wordSpacing == null ? null : String(style.wordSpacing);
    case "direction":
      return style.direction ?? null;
    case "pathLength":
      return style.pathLength == null ? null : String(style.pathLength);
    case "overflow":
      return style.overflow ?? null;
    case "isolation":
      return style.isolation ?? null;
    case "mix-blend-mode":
      return style.mixBlendMode ?? null;
    case "transform":
      return style.transform ?? null;
    case "transform-origin":
      return style.transformOrigin ?? null;
    case "vector-effect":
      return style.vectorEffect ?? null;
    case "padding":
      return style.tableCellPadding == null ? null : String(style.tableCellPadding);
    case "padding-left":
      return style.tableCellPaddingLeft == null ? null : String(style.tableCellPaddingLeft);
    case "padding-right":
      return style.tableCellPaddingRight == null ? null : String(style.tableCellPaddingRight);
    case "padding-top":
      return style.tableCellPaddingTop == null ? null : String(style.tableCellPaddingTop);
    case "padding-bottom":
      return style.tableCellPaddingBottom == null ? null : String(style.tableCellPaddingBottom);
    case "vertical-align":
      return style.tableCellVerticalAlign ?? null;
    case "white-space":
      return style.tableCellNowrap ? "nowrap" : null;
    default:
      return null;
  }
}

function cascadedDeclarations(element: Element, css: CssRule[], aliases: Record<string, string> = {}, includePresentation = true): Record<string, string> {
  const declarations: Record<string, string> = {};
  const priorities = new Map<string, [number, number, number, number, number]>();
  const apply = (name: string, declaration: CssDeclaration, specificity: [number, number, number, number], order: number) => {
    if (!name) return;
    if (name.toLowerCase() === "font") {
      for (const [fontName, fontValue] of Object.entries(parseFontShorthand(declaration.value))) {
        apply(fontName, { value: fontValue, important: declaration.important }, specificity, order);
      }
    }
    const priority: [number, number, number, number, number] = [declaration.important ? 1 : 0, specificity[0], specificity[1], specificity[2], order];
    const current = priorities.get(name) ?? [-1, -1, -1, -1, -1];
    if (comparePriority(priority, current) < 0) return;
    declarations[name] = declaration.value;
    priorities.set(name, priority);
  };
  if (includePresentation) {
    for (const attr of Array.from(element.attributes)) {
      apply(attr.name, { value: attr.value, important: false }, [0, 0, 0, 0], -1);
    }
    for (const [attr, name] of Object.entries(aliases)) {
      const attrValue = element.getAttribute(attr);
      if (attrValue != null) apply(name, { value: attr === "nowrap" ? "nowrap" : attrValue, important: false }, [0, 0, 0, 0], -1);
    }
  }
  for (const rule of css) {
    if (!matchesSelector(element, rule.selector)) continue;
    for (const [name, declaration] of Object.entries(rule.declarations)) {
      apply(name, declaration, [0, ...rule.specificity], rule.order);
    }
  }
  for (const [name, declaration] of Object.entries(parseStyleDeclarations(element.getAttribute("style")))) {
    apply(name, declaration, [1, 0, 0, 0], 1_000_000);
  }
  return declarations;
}

function comparePriority(left: [number, number, number, number, number], right: [number, number, number, number, number]): number {
  for (let index = 0; index < left.length; index += 1) {
    const delta = (left[index] ?? 0) - (right[index] ?? 0);
    if (delta !== 0) return delta;
  }
  return 0;
}

function matchesSelector(element: Element, selector: string): boolean {
  try {
    if (element.matches(selector)) return true;
  } catch (_) {
    // Fall through to the namespace-tolerant matcher below.
  }
  return fallbackMatchesSelector(element, selector);
}

function fallbackMatchesSelector(element: Element, selector: string): boolean {
  const parts = selectorParts(selector);
  if (!parts.length) return false;
  return selectorPartMatchesFrom(element, parts, parts.length - 1);
}

function selectorPartMatchesFrom(element: Element | null, parts: string[], index: number): boolean {
  if (!element || index < 0) return index < 0;
  const part = parts[index];
  if (!part) return false;
  if (part === ">") return selectorPartMatchesFrom(element.parentElement, parts, index - 1);
  if (!simpleSelectorMatches(element, part)) return false;
  if (index === 0) return true;
  const combinator = parts[index - 1];
  if (combinator === ">") return selectorPartMatchesFrom(element.parentElement, parts, index - 2);
  let ancestor = element.parentElement;
  while (ancestor) {
    if (selectorPartMatchesFrom(ancestor, parts, index - 1)) return true;
    ancestor = ancestor.parentElement;
  }
  return false;
}

function simpleSelectorMatches(element: Element, selector: string): boolean {
  let normalized = selector.trim();
  if (!normalized) return true;
  for (const body of pseudoBodies(normalized, "not")) {
    if (selectorList(body).some((item) => simpleSelectorMatches(element, item))) return false;
  }
  for (const name of ["is", "where"]) {
    const bodies = pseudoBodies(normalized, name);
    if (bodies.length && !bodies.some((body) => selectorList(body).some((item) => simpleSelectorMatches(element, item)))) return false;
  }
  normalized = normalized.replace(/:(?:not|is|where)\([^)]*\)/g, "");
  if (normalized === "*") return true;
  const attrs = [...normalized.matchAll(/\[([^\]]+)\]/g)].map((match) => match[1] || "");
  normalized = normalized.replace(/\[[^\]]+\]/g, "");
  const idMatches = [...normalized.matchAll(/#([A-Za-z_][\w:-]*)/g)].map((match) => match[1]).filter((item): item is string => Boolean(item));
  const classMatches = [...normalized.matchAll(/\.([A-Za-z_][\w:-]*)/g)].map((match) => match[1]).filter((item): item is string => Boolean(item));
  const tag = normalized.replace(/#[A-Za-z_][\w:-]*/g, "").replace(/\.[A-Za-z_][\w:-]*/g, "").trim();
  if (tag && tag !== "*" && tag.toLowerCase() !== element.localName.toLowerCase()) return false;
  if (idMatches.length && !idMatches.includes(element.getAttribute("id") || "")) return false;
  const classes = new Set((element.getAttribute("class") || "").split(/\s+/).filter(Boolean));
  if (!classMatches.every((item) => classes.has(item))) return false;
  return attrs.every((attr) => attributeSelectorMatches(element, attr));
}

function attributeSelectorMatches(element: Element, selector: string): boolean {
  const match = selector.match(/^\s*([\w:-]+)\s*(?:([~|^$*]?=)\s*(?:"([^"]*)"|'([^']*)'|([^\]\s]+)))?\s*$/);
  if (!match) return false;
  const name = match[1] || "";
  const operator = match[2] || "";
  const expected = match[3] ?? match[4] ?? match[5] ?? "";
  const actual = element.getAttribute(name);
  if (!operator) return actual != null;
  if (actual == null) return false;
  if (operator === "=") return actual === expected;
  if (operator === "~=") return actual.split(/\s+/).includes(expected);
  if (operator === "|=") return actual === expected || actual.startsWith(`${expected}-`);
  if (operator === "^=") return actual.startsWith(expected);
  if (operator === "$=") return actual.endsWith(expected);
  if (operator === "*=") return actual.includes(expected);
  return false;
}

function selectorParts(selector: string): string[] {
  const parts: string[] = [];
  let current = "";
  let quote: string | null = null;
  let parenDepth = 0;
  let bracketDepth = 0;
  for (const char of selector.trim()) {
    if (quote) {
      current += char;
      if (char === quote) quote = null;
      continue;
    }
    if (char === "\"" || char === "'") {
      quote = char;
      current += char;
      continue;
    }
    if (char === "(") parenDepth += 1;
    if (char === ")" && parenDepth > 0) parenDepth -= 1;
    if (char === "[") bracketDepth += 1;
    if (char === "]" && bracketDepth > 0) bracketDepth -= 1;
    if (parenDepth === 0 && bracketDepth === 0 && (char === ">" || /\s/.test(char))) {
      if (current.trim()) {
        parts.push(current.trim());
        current = "";
      }
      if (char === ">") parts.push(">");
      continue;
    }
    current += char;
  }
  if (current.trim()) parts.push(current.trim());
  return parts;
}

function pseudoBodies(selector: string, name: string): string[] {
  const bodies: string[] = [];
  const token = `:${name}(`;
  let index = 0;
  while (index < selector.length) {
    const start = selector.indexOf(token, index);
    if (start < 0) break;
    let depth = 1;
    let cursor = start + token.length;
    while (cursor < selector.length && depth > 0) {
      if (selector[cursor] === "(") depth += 1;
      if (selector[cursor] === ")") depth -= 1;
      cursor += 1;
    }
    if (depth === 0) bodies.push(selector.slice(start + token.length, cursor - 1));
    index = cursor;
  }
  return bodies;
}

function selectorList(selector: string): string[] {
  return splitCssTopLevel(selector, ",").map((item) => item.trim()).filter(Boolean);
}

function selectorSpecificity(selector: string): [number, number, number] {
  let normalized = selector.replace(/:where\([^)]*\)/g, "");
  const pseudoSpecificities = [...normalized.matchAll(/:(?:is|not)\(([^)]*)\)/g)].map((match) => {
    const options = selectorList(match[1] || "");
    return options.reduce<[number, number, number]>((best, option) => maxSpecificity(best, selectorSpecificity(option)), [0, 0, 0]);
  });
  normalized = normalized.replace(/:(?:is|not)\([^)]*\)/g, "");
  const ids = (normalized.match(/#[A-Za-z_][\w:-]*/g) || []).length;
  const classes = (normalized.match(/\.[A-Za-z_][\w:-]*/g) || []).length;
  const attributes = (normalized.match(/\[[^\]]+\]/g) || []).length;
  const pseudoClasses = (normalized.match(/:[A-Za-z_][\w:-]*/g) || []).length;
  const stripped = normalized
    .replace(/\[[^\]]+\]/g, " ")
    .replace(/#[A-Za-z_][\w:-]*/g, " ")
    .replace(/\.[A-Za-z_][\w:-]*/g, " ")
    .replace(/::?[A-Za-z_][\w:-]*/g, " ");
  const elements = stripped.split(/[\s>+~]+/).filter((part) => /^[A-Za-z_][\w:-]*$/.test(part) && part !== "*").length;
  return pseudoSpecificities.reduce<[number, number, number]>(
    (total, item) => [total[0] + item[0], total[1] + item[1], total[2] + item[2]],
    [ids, classes + attributes + pseudoClasses, elements],
  );
}

function maxSpecificity(left: [number, number, number], right: [number, number, number]): [number, number, number] {
  for (let index = 0; index < left.length; index += 1) {
    const delta = (left[index] ?? 0) - (right[index] ?? 0);
    if (delta > 0) return left;
    if (delta < 0) return right;
  }
  return left;
}

function cssDeclarationList(style: string): string[] {
  return splitCssTopLevel(style, ";");
}

function splitCssTopLevel(value: string, separator: "," | ";"): string[] {
  const parts: string[] = [];
  let current = "";
  let quote: string | null = null;
  let parenDepth = 0;
  let bracketDepth = 0;
  for (const char of value) {
    if (quote) {
      current += char;
      if (char === quote) quote = null;
      continue;
    }
    if (char === "\"" || char === "'") {
      quote = char;
      current += char;
      continue;
    }
    if (char === "(") parenDepth += 1;
    if (char === ")" && parenDepth > 0) parenDepth -= 1;
    if (char === "[") bracketDepth += 1;
    if (char === "]" && bracketDepth > 0) bracketDepth -= 1;
    if (char === separator && parenDepth === 0 && bracketDepth === 0) {
      parts.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  parts.push(current);
  return parts;
}

function styleDeclarations(style: string | null): Record<string, string> {
  return Object.fromEntries(Object.entries(parseStyleDeclarations(style)).map(([name, declaration]) => [name, declaration.value]));
}

function parseStyleDeclarations(style: string | null): Record<string, CssDeclaration> {
  if (!style) return {};
  const declarations: Record<string, CssDeclaration> = {};
  for (const entry of cssDeclarationList(style)) {
    const colon = entry.indexOf(":");
    if (colon <= 0) continue;
    const name = entry.slice(0, colon).trim();
    const rawValue = entry.slice(colon + 1).trim();
    if (!name || !rawValue) continue;
    const important = /\s*!important\s*$/i.test(rawValue);
    const declaration = {
      value: important ? rawValue.replace(/\s*!important\s*$/i, "").trim() : rawValue,
      important,
    };
    addStyleDeclaration(declarations, name, declaration);
  }
  return declarations;
}

function addStyleDeclaration(declarations: Record<string, CssDeclaration>, name: string, declaration: CssDeclaration): void {
  if (name.toLowerCase() === "font") {
    for (const [fontName, fontValue] of Object.entries(parseFontShorthand(declaration.value))) {
      declarations[fontName] = { value: fontValue, important: declaration.important };
    }
  }
  declarations[name] = declaration;
}

function parseFontShorthand(value: string): Record<string, string> {
  const tokens = cssValueTokens(value);
  const result: Record<string, string> = {};
  let sizeIndex = -1;
  let skipNextObliqueAngle = false;
  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index]!;
    if (skipNextObliqueAngle) {
      skipNextObliqueAngle = false;
      if (fontAngleTokenIsSupported(token)) continue;
    }
    const size = token.split("/", 1)[0]!.trim();
    if (fontSizeTokenIsSupported(size)) {
      sizeIndex = index;
      result["font-size"] = size;
      break;
    }
    const normalized = token.trim().toLowerCase();
    if (normalized === "italic" || normalized === "oblique" || normalized.startsWith("oblique ")) {
      result["font-style"] = normalized.startsWith("oblique") ? "oblique" : normalized;
      skipNextObliqueAngle = normalized === "oblique";
    } else if (normalized === "small-caps" || normalized === "all-small-caps") {
      result["font-variant"] = normalized;
    } else if (fontWeightTokenIsSupported(normalized)) {
      result["font-weight"] = normalized;
    }
  }
  if (sizeIndex < 0) return {};
  result["font-style"] ??= "normal";
  result["font-variant"] ??= "normal";
  result["font-weight"] ??= "normal";
  const family = tokens.slice(sizeIndex + 1).join(" ").trim();
  if (family) result["font-family"] = family;
  return result;
}

function cssValueTokens(value: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: string | null = null;
  let parenDepth = 0;
  for (const char of value) {
    if (quote) {
      current += char;
      if (char === quote) quote = null;
      continue;
    }
    if (char === "\"" || char === "'") {
      quote = char;
      current += char;
      continue;
    }
    if (char === "(") parenDepth += 1;
    if (char === ")" && parenDepth > 0) parenDepth -= 1;
    if (parenDepth === 0 && /\s/.test(char)) {
      if (current.trim()) {
        tokens.push(current.trim());
        current = "";
      }
      continue;
    }
    current += char;
  }
  if (current.trim()) tokens.push(current.trim());
  return tokens;
}

function fontSizeTokenIsSupported(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (["xx-small", "x-small", "small", "medium", "large", "x-large", "xx-large"].includes(normalized)) return true;
  if (!/[a-z%]/.test(normalized)) return normalized === "0";
  return Number.isFinite(parseCssLength(value, Number.NaN, Number.NaN));
}

function fontAngleTokenIsSupported(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return parseTransformAngleArg(value) != null && ["deg", "rad", "grad", "turn"].some((unit) => normalized.endsWith(unit));
}

function fontWeightTokenIsSupported(value: string): boolean {
  if (["normal", "bold", "bolder", "lighter"].includes(value)) return true;
  const weight = Number.parseInt(value, 10);
  return /^\d+$/.test(value) && weight >= 1 && weight <= 1000;
}

function strokeStyle(style: SvgStyle): { strokeLineCap: string | null; strokeLineJoin: string | null; strokeMiterlimit: number | null; strokeDasharray: string | null; strokeDashoffset: number | null } {
  return {
    strokeLineCap: style.strokeLineCap ?? null,
    strokeLineJoin: style.strokeLineJoin ?? null,
    strokeMiterlimit: style.strokeMiterlimit ?? null,
    strokeDasharray: style.strokeDasharray ?? null,
    strokeDashoffset: style.strokeDashoffset ?? null,
  };
}

function scaledStrokeStyle(style: SvgStyle, scale: number): SvgStyle {
  if (Math.abs(scale - 1) < 1e-9) return style;
  const next = { ...style };
  if (next.strokeWidth != null) next.strokeWidth *= scale;
  if (next.strokeDasharray) next.strokeDasharray = scaleDasharray(next.strokeDasharray, scale);
  if (next.strokeDashoffset != null) next.strokeDashoffset *= scale;
  return next;
}

function strokeTransformScale(style: SvgStyle, matrix: Matrix): number {
  return style.vectorEffect === "non-scaling-stroke" ? 1 : matrixScale(matrix);
}

function matrixScale(matrix: Matrix): number {
  const [a, b, c, d] = matrix;
  const sx = Math.hypot(a, b);
  const sy = Math.hypot(c, d);
  return sx && sy ? (sx + sy) / 2 : sx || sy || 1;
}

function scaleDasharray(value: string, scale: number): string {
  const nums = dasharrayNumbers(value);
  if (!nums) return value;
  return nums.map((item) => formatNumber(item * scale)).join(" ");
}

function scaledTextMetricsStyle(style: SvgStyle, scale: number): SvgStyle {
  if (Math.abs(scale - 1) < 1e-9) return style;
  const next = { ...style };
  if (next.fontSize != null) next.fontSize *= scale;
  if (next.textLength != null) next.textLength *= scale;
  if (next.letterSpacing != null) next.letterSpacing *= scale;
  if (next.wordSpacing != null) next.wordSpacing *= scale;
  if (next.textDecorationThickness != null) next.textDecorationThickness *= scale;
  return next;
}

function scaledPathLengthDashStyle(style: SvgStyle, scale: number): SvgStyle {
  if (Math.abs(scale - 1) < 1e-9 || !style.strokeDasharray) return style;
  const next = { ...style };
  next.strokeDasharray = scaleDasharray(style.strokeDasharray, scale);
  if (next.strokeDashoffset != null) next.strokeDashoffset *= scale;
  return next;
}

function pathLengthScale(style: SvgStyle, element: Element, tag: string, viewport: Viewport, points: [number, number][] | null = null, css: CssRule[] = [], inheritedStyle: SvgStyle = {}): number {
  const declared = style.pathLength ?? normalizePathLength(element.getAttribute("pathLength"));
  if (!declared || declared <= 0) return 1;
  const actual = pathActualLength(element, tag, viewport, points, css, inheritedStyle);
  return actual && actual > 0 ? actual / declared : 1;
}

function pathActualLength(element: Element, tag: string, viewport: Viewport, points: [number, number][] | null, css: CssRule[] = [], inheritedStyle: SvgStyle = {}): number | null {
  if (tag === "line") {
    const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
    const x1 = cascadedGeom(element, declarations, "x1", "x", viewport);
    const y1 = cascadedGeom(element, declarations, "y1", "y", viewport);
    const x2 = cascadedGeom(element, declarations, "x2", "x", viewport);
    const y2 = cascadedGeom(element, declarations, "y2", "y", viewport);
    return Math.hypot(x2 - x1, y2 - y1);
  }
  if (points && points.length >= 2) return polylineLength(points, tag === "polygon");
  return null;
}

function polylineLength(points: [number, number][], closed: boolean): number {
  let total = 0;
  for (let index = 1; index < points.length; index += 1) total += pointDistance(points[index - 1]!, points[index]!);
  if (closed && points.length > 2) total += pointDistance(points[points.length - 1]!, points[0]!);
  return total;
}

function pointDistance(a: [number, number], b: [number, number]): number {
  return Math.hypot(b[0] - a[0], b[1] - a[1]);
}

function normalizePathLength(value: string | null): number | null {
  if (value == null) return null;
  const parsed = Number.parseFloat(value.trim());
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function normalizeVectorEffect(value: string): string | null {
  const normalized = value.trim().toLowerCase().split(/\s+/).join(" ");
  return normalized === "non-scaling-stroke" ? normalized : null;
}

function normalizeStrokeLineCap(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  return ["butt", "round", "square"].includes(normalized) ? normalized : null;
}

function normalizeStrokeLineJoin(value: string): string | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === "miter-clip") return "miter";
  return ["miter", "round", "bevel"].includes(normalized) ? normalized : null;
}

function normalizeStrokeMiterlimit(value: string): number | null {
  const parsed = Number.parseFloat(value.trim());
  return Number.isFinite(parsed) && parsed >= 1 ? parsed : null;
}

function normalizeStrokeWidth(value: string, basis: number, fallback: number): number {
  const parsed = parseCssLength(value, basis, Number.NaN);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function normalizeDisplay(value: string): string | null {
  const normalized = value.trim().toLowerCase().split(/\s+/).join(" ");
  return normalized === "none" ? "none" : null;
}

function normalizeVisibility(value: string): string | null {
  const normalized = value.trim().toLowerCase().split(/\s+/).join(" ");
  if (normalized === "hidden" || normalized === "collapse") return normalized;
  if (normalized === "visible") return "visible";
  return null;
}

function normalizeOverflow(value: string): string | null {
  const normalized = value.trim().toLowerCase().split(/\s+/).join(" ");
  return ["hidden", "clip", "scroll", "auto"].includes(normalized) ? "hidden" : normalized === "visible" ? "visible" : null;
}

function normalizeStrokeDasharray(value: string, basis = rootFontSize): string | null {
  const normalized = value.trim();
  if (!normalized || normalized === "none") return null;
  const nums = dasharrayNumbers(normalized, basis);
  return nums ? nums.map(formatNumber).join(" ") : null;
}

function normalizeStrokeDasharrayWithOffset(value: string, offset: number, basis = rootFontSize): string | null {
  const nums = dasharrayWithOffset(value, offset, basis);
  return nums ? nums.map(formatNumber).join(" ") : null;
}

function normalizeSpacingLength(value: string, basis = rootFontSize): number | null {
  const normalized = value.trim().toLowerCase();
  if (!normalized || normalized === "normal") return null;
  const parsed = parseCssLength(normalized, basis, Number.NaN);
  return Number.isFinite(parsed) ? parsed : null;
}

function dasharrayNumbers(value: string, basis = rootFontSize): number[] | null {
  const parts = value.replaceAll(",", " ").trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return null;
  const nums = parts.map((part) => parseCssLength(part, basis, Number.NaN));
  return nums.every((item) => Number.isFinite(item) && item >= 0) ? nums : null;
}

function dasharrayWithOffset(value: string, offset: number, basis = rootFontSize): number[] | null {
  let nums = dasharrayNumbers(value, basis);
  if (!nums?.length || nums.reduce((sum, item) => sum + item, 0) <= 0) return null;
  if (nums.length % 2 === 1) nums = nums.concat(nums);
  const period = nums.reduce((sum, item) => sum + item, 0);
  if (period <= 0) return null;
  const phase = ((offset % period) + period) % period;
  if (numbersClose(phase, 0)) return nums;
  let cursor = 0;
  for (let index = 0; index < nums.length; index += 1) {
    const length = nums[index]!;
    const end = cursor + length;
    if (phase < end || numbersClose(phase, end)) {
      if (numbersClose(phase, end)) {
        cursor = end;
        continue;
      }
      if (index % 2 === 1) {
        const remainingGap = end - phase;
        if (numbersClose(remainingGap, 0)) {
          cursor = end;
          continue;
        }
        const shifted = [0, remainingGap, ...nums.slice(index + 1), ...nums.slice(0, index)];
        const consumedGap = phase - cursor;
        if (!numbersClose(consumedGap, 0)) shifted.push(consumedGap);
        if (shifted.length % 2 === 1) shifted.push(0);
        return shifted;
      }
      const remaining = end - phase;
      if (numbersClose(remaining, 0)) {
        cursor = end;
        continue;
      }
      const shifted = [remaining, ...nums.slice(index + 1), ...nums.slice(0, index)];
      const consumed = phase - cursor;
      if (!numbersClose(consumed, 0)) shifted.push(consumed);
      if (shifted.length % 2 === 1) shifted.push(0);
      return shifted;
    }
    cursor = end;
  }
  return null;
}

function numbersClose(left: number, right: number, tolerance = 1e-9): boolean {
  return Math.abs(left - right) < tolerance;
}

function normalizePaint(value: string, refs: Map<string, Element> = new Map(), style: SvgStyle = {}, css: CssRule[] = []): string | null {
  return normalizePaintValue(value, refs, style, css)?.color ?? null;
}

function normalizePaintValue(value: string, refs: Map<string, Element> = new Map(), style: SvgStyle = {}, css: CssRule[] = []): { color: string; alpha: number | null } | null {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "none" || trimmed === "transparent") return null;
  const contextPaint = contextPaintValue(trimmed, style);
  if (contextPaint) return contextPaint;
  const ref = paintUrlRef(trimmed);
  if (ref) {
    const server = paintServerColor(ref.id, refs, style, new Set(), css);
    if (server) return { color: server, alpha: cssColorAlpha(server) };
    return normalizePaintValue(ref.fallback, refs, style, css);
  }
  const color = parseCssColor(trimmed, style) ?? trimmed;
  return { color, alpha: cssColorAlpha(trimmed) };
}

function contextPaintValue(value: string, style: SvgStyle): { color: string; alpha: number | null } | null {
  const normalized = value.trim().toLowerCase();
  if (normalized === "context-fill" && style.fill) return { color: style.fill, alpha: style.fillAlpha ?? cssColorAlpha(style.fill) };
  if (normalized === "context-stroke" && style.stroke) return { color: style.stroke, alpha: style.strokeAlpha ?? cssColorAlpha(style.stroke) };
  return null;
}

function paintServerColor(id: string, refs: Map<string, Element>, style: SvgStyle, seen: Set<string> = new Set(), css: CssRule[] = []): string | null {
  if (seen.has(id)) return null;
  const element = refs.get(id);
  if (!element) return null;
  const tag = localName(element);
  if (tag === "pattern") return averageColor(patternColors(element, refs, {}, new Set([...seen, id]), css));
  if (tag !== "linearGradient" && tag !== "radialGradient") return null;
  const nextSeen = new Set([...seen, id]);
  const href = hrefValue(element);
  const inheritedStops = href.startsWith("#") ? gradientStops(refs.get(href.slice(1)), refs, style, nextSeen, css) : [];
  const stops = inheritedStops.concat(gradientStops(element, refs, style, nextSeen, css));
  if (!stops.length) return null;
  if (tag === "radialGradient") return stops[stops.length - 1] ?? null;
  const rgb = stops.map(hexToRgb).filter((item): item is [number, number, number] => Boolean(item));
  if (!rgb.length) return null;
  const count = rgb.length;
  return rgbToHex([
    Math.round(rgb.reduce((sum, item) => sum + item[0], 0) / count),
    Math.round(rgb.reduce((sum, item) => sum + item[1], 0) / count),
    Math.round(rgb.reduce((sum, item) => sum + item[2], 0) / count),
  ]);
}

function patternColors(element: Element, refs: Map<string, Element>, inheritedStyle: SvgStyle, seen: Set<string>, css: CssRule[] = []): string[] {
  const colors: string[] = [];
  for (const child of Array.from(element.children)) {
    const tag = localName(child);
    const style = simpleElementStyle(child, inheritedStyle, refs, seen, css);
    if (style.display === "none" || style.visibility === "hidden" || style.visibility === "collapse") continue;
    if (tag === "g" || tag === "svg" || tag === "a") {
      colors.push(...patternColors(child, refs, style, seen, css));
      continue;
    }
    if (!["rect", "circle", "ellipse", "path", "polygon", "polyline", "text", "tspan", "line"].includes(tag)) continue;
    if (tag !== "line" && style.fill && style.fillAlpha !== 0) colors.push(style.fill);
    if (style.stroke && style.strokeAlpha !== 0) colors.push(style.stroke);
    colors.push(...patternColors(child, refs, style, seen, css));
  }
  return colors;
}

function simpleElementStyle(element: Element, inheritedStyle: SvgStyle, refs: Map<string, Element>, seen: Set<string>, css: CssRule[] = []): SvgStyle {
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
  const value = (name: string): string | null => declarations[name] ?? element.getAttribute(name) ?? null;
  const fill = value("fill");
  const stroke = value("stroke");
  const display = value("display");
  const visibility = value("visibility");
  const opacity = value("opacity");
  const fillOpacity = value("fill-opacity");
  const strokeOpacity = value("stroke-opacity");
  const next: SvgStyle = { ...inheritedStyle };
  const opacityAlpha = parseAlpha(opacity);
  if (display != null) next.display = normalizeDisplay(display);
  if (visibility != null) next.visibility = normalizeVisibility(visibility);
  if (fill != null) next.fill = normalizePatternPaint(fill, refs, next, seen, css);
  if (stroke != null) next.stroke = normalizePatternPaint(stroke, refs, next, seen, css);
  if (fill != null || opacityAlpha != null || fillOpacity != null) next.fillAlpha = combinedAlpha(opacityAlpha, parseAlpha(fillOpacity), next.fillAlpha);
  if (stroke != null || opacityAlpha != null || strokeOpacity != null) next.strokeAlpha = combinedAlpha(opacityAlpha, parseAlpha(strokeOpacity), next.strokeAlpha);
  return next;
}

function normalizePatternPaint(value: string, refs: Map<string, Element>, style: SvgStyle, seen: Set<string>, css: CssRule[] = []): string | null {
  const trimmed = value.trim();
  if (!trimmed || trimmed === "none" || trimmed === "transparent") return null;
  const ref = paintUrlRef(trimmed);
  if (ref) {
    const targetId = ref.id;
    return seen.has(targetId) ? normalizePaint(ref.fallback, refs, style, css) : paintServerColor(targetId, refs, style, seen, css) ?? normalizePaint(ref.fallback, refs, style, css);
  }
  return normalizeStopColor(trimmed, style);
}

function averageColor(colors: string[]): string | null {
  const rgb = colors.map(hexToRgb).filter((item): item is [number, number, number] => Boolean(item));
  if (!rgb.length) return null;
  const count = rgb.length;
  return rgbToHex([
    Math.round(rgb.reduce((sum, item) => sum + item[0], 0) / count),
    Math.round(rgb.reduce((sum, item) => sum + item[1], 0) / count),
    Math.round(rgb.reduce((sum, item) => sum + item[2], 0) / count),
  ]);
}

function gradientStops(element: Element | undefined, refs: Map<string, Element>, style: SvgStyle, seen: Set<string>, css: CssRule[] = []): string[] {
  if (!element) return [];
  const tag = localName(element);
  if (tag !== "linearGradient" && tag !== "radialGradient") return [];
  const colors: string[] = [];
  const gradientDeclarations = resolvedCascadedDeclarations(element, css, style);
  const inheritedStopColor = gradientDeclarations["stop-color"] ?? element.getAttribute("stop-color") ?? null;
  const inheritedStopOpacity = gradientDeclarations["stop-opacity"] ?? element.getAttribute("stop-opacity") ?? null;
  const gradientColor = gradientDeclarations.color ?? element.getAttribute("color") ?? null;
  const gradientStyle: SvgStyle = gradientColor ? { ...style, color: parseCssColor(gradientColor, style) ?? style.color ?? null } : style;
  const href = hrefValue(element);
  if (href.startsWith("#")) {
    const inherited = refs.get(href.slice(1));
    const inheritedId = inherited?.getAttribute("id") || "";
    if (inherited && inheritedId && !seen.has(inheritedId)) colors.push(...gradientStops(inherited, refs, gradientStyle, new Set([...seen, inheritedId]), css));
  }
  for (const stop of Array.from(element.children)) {
    if (localName(stop) !== "stop") continue;
    const declarations = resolvedCascadedDeclarations(stop, css, gradientStyle);
    const color = declarations["stop-color"] ?? stop.getAttribute("stop-color") ?? inheritedStopColor ?? "#000000";
    const stopOpacity = declarations["stop-opacity"] ?? stop.getAttribute("stop-opacity") ?? inheritedStopOpacity;
    const stopOpacityAlpha = parseAlpha(stopOpacity);
    const normalized = normalizeStopColor(color, gradientStyle);
    const colorAlpha = cssColorAlpha(color);
    if (normalized && combinedAlpha(stopOpacityAlpha, colorAlpha) !== 0) colors.push(normalized);
  }
  return colors;
}

function normalizeStopColor(value: string, style: SvgStyle): string | null {
  return parseCssColor(value, style);
}

function parseCssColor(value: string | null, style: SvgStyle = {}): string | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  const lower = trimmed.toLowerCase();
  if (lower === "none" || lower === "transparent") return null;
  if (lower === "currentcolor") return style.color ?? style.fill ?? style.stroke ?? "#000000";
  if (lower in namedColors) return namedColors[lower] ?? null;
  if (/^#[0-9a-f]{3}$/i.test(trimmed)) return `#${trimmed.slice(1).split("").map((char) => char + char).join("")}`;
  if (/^#[0-9a-f]{4}$/i.test(trimmed)) return `#${trimmed.slice(1, 4).split("").map((char) => char + char).join("")}`;
  if (/^#[0-9a-f]{6}$/i.test(trimmed)) return trimmed.slice(0, 7);
  if (/^#[0-9a-f]{8}$/i.test(trimmed)) return trimmed.slice(0, 7);
  const rgb = parseRgbFunction(trimmed);
  if (rgb) return rgbToHex(rgb);
  const hsl = parseHslFunction(trimmed);
  if (hsl) return rgbToHex(hsl);
  return null;
}

function cssColorAlpha(value: string | null): number | null {
  if (!value) return null;
  const trimmed = value.trim();
  if (/^#[0-9a-f]{4}$/i.test(trimmed)) return Number.parseInt(trimmed.slice(4, 5).repeat(2), 16) / 255;
  if (/^#[0-9a-f]{8}$/i.test(trimmed)) return Number.parseInt(trimmed.slice(7, 9), 16) / 255;
  const functionMatch = trimmed.match(/^(?:rgba|hsla?)\(([^)]+)\)$/i);
  if (!functionMatch) return null;
  const parts = colorFunctionParts(functionMatch[1] || "");
  return parts.length >= 4 ? parseAlpha(parts[3]!) : null;
}

function parseAlpha(value: string | null): number | null {
  if (value == null) return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  return cssAlpha(trimmed);
}

function combinedAlpha(...values: (number | null | undefined)[]): number | null {
  let alpha = 1;
  let seen = false;
  for (const value of values) {
    if (value == null) continue;
    alpha *= clamp(value, 0, 1);
    seen = true;
  }
  return seen ? alpha : null;
}

function parseRgbFunction(value: string): [number, number, number] | null {
  const match = value.match(/^rgba?\(([^)]+)\)$/i);
  if (!match) return null;
  const parts = colorFunctionParts(match[1] || "");
  if (parts.length < 3) return null;
  return [cssChannel(parts[0]!), cssChannel(parts[1]!), cssChannel(parts[2]!)];
}

function parseHslFunction(value: string): [number, number, number] | null {
  const match = value.match(/^hsla?\(([^)]+)\)$/i);
  if (!match) return null;
  const parts = colorFunctionParts(match[1] || "");
  if (parts.length < 3) return null;
  return hslToRgb(parts[0]!, cssAlpha(parts[1]!), cssAlpha(parts[2]!));
}

function colorFunctionParts(value: string): string[] {
  return value.replaceAll(",", " ").replace("/", " ").trim().split(/\s+/).filter(Boolean);
}

function cssChannel(value: string): number {
  if (value.endsWith("%")) return Math.round(clamp(Number.parseFloat(value) || 0, 0, 100) * 2.55);
  return Math.round(clamp(Number.parseFloat(value) || 0, 0, 255));
}

function cssAlpha(value: string): number {
  if (value.endsWith("%")) return clamp((Number.parseFloat(value) || 0) / 100, 0, 1);
  return clamp(Number.parseFloat(value) || 0, 0, 1);
}

function hslToRgb(hueValue: string, saturation: number, lightness: number): [number, number, number] {
  const hue = cssHueDegrees(hueValue) / 360;
  if (saturation === 0) {
    const channel = Math.round(lightness * 255);
    return [channel, channel, channel];
  }
  const q = lightness < 0.5 ? lightness * (1 + saturation) : lightness + saturation - lightness * saturation;
  const p = 2 * lightness - q;
  const channel = (offset: number) => {
    const t = (hue + offset + 1) % 1;
    const value = t < 1 / 6 ? p + (q - p) * 6 * t : t < 1 / 2 ? q : t < 2 / 3 ? p + (q - p) * (2 / 3 - t) * 6 : p;
    return Math.round(value * 255 + 1e-9);
  };
  return [channel(1 / 3), channel(0), channel(-1 / 3)];
}

function cssHueDegrees(value: string): number {
  const number = Number.parseFloat(value) || 0;
  if (value.endsWith("turn")) return number * 360;
  if (value.endsWith("rad")) return (number * 180) / Math.PI;
  if (value.endsWith("grad")) return number * 0.9;
  return number;
}

function paintUrlRef(value: string): { id: string; fallback: string } | null {
  const match = value.match(/^url\(\s*['"]?#([^'")\s]+)['"]?\s*\)\s*(.*)$/);
  return match ? { id: match[1]!, fallback: match[2]?.trim() || "" } : null;
}

function hexToRgb(value: string): [number, number, number] | null {
  const normalized = normalizeStopColor(value, {});
  if (!normalized) return null;
  const raw = normalized.slice(1);
  return [Number.parseInt(raw.slice(0, 2), 16), Number.parseInt(raw.slice(2, 4), 16), Number.parseInt(raw.slice(4, 6), 16)];
}

function rgbToHex(rgb: [number, number, number]): string {
  return `#${rgb.map((value) => clamp(Math.round(value), 0, 255).toString(16).padStart(2, "0")).join("")}`;
}

function parseLength(value: string | null, fallback = 0): number {
  if (!value) return fallback;
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function formatNumber(value: number): string {
  return String(Math.round(value * 10000) / 10000);
}

function parseFontSize(value: string | null, inherited = rootFontSize): number {
  if (!value) return inherited;
  const normalized = value.trim().toLowerCase();
  const keywords: Record<string, number> = {
    "xx-small": 9,
    "x-small": 10,
    small: 13,
    medium: 16,
    large: 18,
    "x-large": 24,
    "xx-large": 32,
  };
  return keywords[normalized] ?? parseCssLength(value, inherited, inherited);
}

function normalizeFontFamily(value: string): string {
  const first = splitCssTopLevel(value, ",")[0]?.trim() || value.trim();
  return first.replace(/^['"]|['"]$/g, "");
}

function parseCssLength(value: string | null, basis = Number.NaN, fallback = 0): number {
  if (!value) return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  const lower = trimmed.toLowerCase();
  if (lower.startsWith("calc(") && trimmed.endsWith(")")) {
    const calculated = calcLength(trimmed.slice(5, -1), basis);
    return calculated == null ? fallback : calculated;
  }
  const functionValue = cssLengthFunction(lower, basis);
  if (functionValue != null) return functionValue;
  if (lower.endsWith("%")) {
    const percent = Number.parseFloat(lower.slice(0, -1));
    return Number.isFinite(percent) && Number.isFinite(basis) ? (basis * percent) / 100 : fallback;
  }
  if (lower.endsWith("rem")) {
    const number = Number.parseFloat(lower.slice(0, -3));
    return Number.isFinite(number) ? number * rootFontSize : fallback;
  }
  if (lower.endsWith("em")) {
    const number = Number.parseFloat(lower.slice(0, -2));
    return Number.isFinite(number) && Number.isFinite(basis) ? number * basis : fallback;
  }
  const absolute = parseAbsoluteLength(trimmed);
  return Number.isFinite(absolute) ? absolute : fallback;
}

function calcLength(body: string, basis: number): number | null {
  const addends = splitCalcAddends(body);
  if (!addends.length) return null;
  let total = 0;
  for (const [sign, term] of addends) {
    const value = calcProduct(term, basis);
    if (value == null) return null;
    total += sign * value;
  }
  return total;
}

function splitCalcAddends(value: string): [number, string][] {
  const result: [number, string][] = [];
  let current = "";
  let sign = 1;
  let depth = 0;
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index]!;
    if (char === "(") depth += 1;
    if (char === ")" && depth > 0) depth -= 1;
    if ((char === "+" || char === "-") && depth === 0 && !calcSignIsUnary(value, index) && !/[eE]$/.test(current.trim())) {
      if (current.trim()) result.push([sign, current.trim()]);
      current = "";
      sign = char === "-" ? -1 : 1;
      continue;
    }
    current += char;
  }
  if (current.trim()) result.push([sign, current.trim()]);
  return result;
}

function calcProduct(value: string, basis: number): number | null {
  const factors = splitCalcFactors(value);
  if (!factors.length) return null;
  let result = factorLength(factors[0]![1], basis);
  if (result == null) return null;
  for (let index = 1; index < factors.length; index += 1) {
    const [operator, raw] = factors[index]!;
    const number = operator === "*" ? factorNumber(raw, basis) : factorDivisor(raw, basis);
    if (number == null) return null;
    result = operator === "*" ? result * number : result / number;
  }
  return Number.isFinite(result) ? result : null;
}

function splitCalcFactors(value: string): [string, string][] {
  const result: [string, string][] = [];
  let current = "";
  let operator = "*";
  let depth = 0;
  for (const char of value) {
    if (char === "(") depth += 1;
    if (char === ")" && depth > 0) depth -= 1;
    if ((char === "*" || char === "/") && depth === 0) {
      if (current.trim()) result.push([operator, current.trim()]);
      operator = char;
      current = "";
      continue;
    }
    current += char;
  }
  if (current.trim()) result.push([operator, current.trim()]);
  return result;
}

function factorLength(value: string, basis: number): number | null {
  const trimmed = stripOuterParens(value.trim());
  if (trimmed.toLowerCase().startsWith("calc(") && trimmed.endsWith(")")) return calcLength(trimmed.slice(5, -1), basis);
  if (splitCalcAddends(trimmed).length > 1) return calcLength(trimmed, basis);
  return parseCssLength(trimmed, basis, Number.NaN);
}

function factorNumber(value: string, basis: number): number | null {
  const trimmed = stripOuterParens(value.trim());
  const parsed = Number.parseFloat(trimmed);
  if (Number.isFinite(parsed) && !/[a-z%]/i.test(trimmed)) return parsed;
  return factorLength(trimmed, basis);
}

function factorDivisor(value: string, basis: number): number | null {
  const parsed = factorNumber(value, basis);
  return parsed == null || Math.abs(parsed) < 0.000001 ? null : parsed;
}

function cssLengthFunction(value: string, basis: number): number | null {
  const nameEnd = value.indexOf("(");
  if (nameEnd <= 0 || !value.endsWith(")")) return null;
  const name = value.slice(0, nameEnd);
  if (!["min", "max", "clamp"].includes(name)) return null;
  const args = splitCssTopLevel(value.slice(nameEnd + 1, -1), ",").map((item) => parseCssLength(item, basis, Number.NaN));
  if (args.some((item) => !Number.isFinite(item))) return null;
  if (name === "min") return Math.min(...args);
  if (name === "max") return Math.max(...args);
  if (name === "clamp" && args.length >= 3) return Math.min(Math.max(args[1]!, args[0]!), args[2]!);
  return null;
}

function stripOuterParens(value: string): string {
  let trimmed = value;
  while (trimmed.startsWith("(") && trimmed.endsWith(")")) {
    const inner = trimmed.slice(1, -1);
    if (splitCssTopLevel(inner, ",").length !== 1) break;
    trimmed = inner.trim();
  }
  return trimmed;
}

function calcSignIsUnary(value: string, index: number): boolean {
  const previous = value.slice(0, index).trimEnd();
  return !previous || /[+\-*/(]$/.test(previous);
}

function parseAbsoluteLength(value: string | null, fallback = Number.NaN): number {
  if (!value) return fallback;
  const trimmed = value.trim().toLowerCase();
  const match = trimmed.match(/^([+-]?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)([a-z]*)$/);
  if (!match) return fallback;
  const number = Number.parseFloat(match[1] || "");
  if (!Number.isFinite(number)) return fallback;
  const unit = match[2] || "";
  const scale: Record<string, number> = {
    "": 1,
    px: 1,
    in: 96,
    cm: 96 / 2.54,
    mm: 96 / 25.4,
    q: 96 / 101.6,
    pt: 96 / 72,
    pc: 16,
  };
  return scale[unit] == null ? fallback : number * scale[unit];
}

function supportedDataImage(value: string): boolean {
  return dataImageBytes(value) != null;
}

function imagePreserveAspectRatioRect(x: number, y: number, width: number, height: number, href: string, value: string | null): { x: number; y: number; width: number; height: number; srcRect: [number, number, number, number] | null } {
  if (!value) return { x, y, width, height, srcRect: null };
  const [align, meetOrSlice] = parsePreserveAspectRatio(value);
  if (align === "none") return { x, y, width, height, srcRect: null };
  const intrinsic = dataImageDimensions(href);
  if (!intrinsic || intrinsic.width <= 0 || intrinsic.height <= 0 || width <= 0 || height <= 0) return { x, y, width, height, srcRect: null };
  if (meetOrSlice === "slice") return { x, y, width, height, srcRect: imageSliceSrcRect(intrinsic.width, intrinsic.height, width, height, align) };
  const scale = Math.min(width / intrinsic.width, height / intrinsic.height);
  const renderedWidth = intrinsic.width * scale;
  const renderedHeight = intrinsic.height * scale;
  return {
    x: x + aspectAlignmentOffset(align.slice(1, 4), width - renderedWidth),
    y: y + aspectAlignmentOffset(align.slice(5, 8), height - renderedHeight),
    width: renderedWidth,
    height: renderedHeight,
    srcRect: null,
  };
}

function imageSliceSrcRect(imageWidth: number, imageHeight: number, viewportWidth: number, viewportHeight: number, align: string): [number, number, number, number] | null {
  const imageAspect = imageWidth / imageHeight;
  const viewportAspect = viewportWidth / viewportHeight;
  if (numbersClose(imageAspect, viewportAspect)) return null;
  if (imageAspect > viewportAspect) {
    const crop = 1 - viewportAspect / imageAspect;
    const [before, after] = alignedCrop(crop, align.slice(1, 4));
    return [Math.round(before * 100000), 0, Math.round(after * 100000), 0];
  }
  const crop = 1 - imageAspect / viewportAspect;
  const [before, after] = alignedCrop(crop, align.slice(5, 8));
  return [0, Math.round(before * 100000), 0, Math.round(after * 100000)];
}

function alignedCrop(total: number, alignment: string): [number, number] {
  if (alignment === "Min") return [0, total];
  if (alignment === "Max") return [total, 0];
  return [total / 2, total / 2];
}

function dataImageDimensions(uri: string): { width: number; height: number } | null {
  const match = uri.match(/^data:image\/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=\s]+)$/i);
  if (!match) return null;
  const kind = match[1]!.toLowerCase();
  const bytes = dataImageBytes(uri);
  if (!bytes) return null;
  if (kind === "png") return pngDimensions(bytes);
  if (kind === "gif") return bytes.length >= 10 ? { width: le16(bytes, 6), height: le16(bytes, 8) } : null;
  if (kind === "webp") return webpDimensions(bytes);
  return jpegDimensions(bytes);
}

function dataImageBytes(value: string): Uint8Array | null {
  const match = value.match(/^data:image\/(?:png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=\s]+)$/i);
  return match ? base64PayloadBytes(match[1] || "") : null;
}

function base64PayloadBytes(value: string): Uint8Array | null {
  const payload = value.replace(/\s+/g, "");
  if (!payload || payload.length % 4 !== 0) return null;
  try {
    return base64Bytes(payload);
  } catch {
    return null;
  }
}

function pngDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  return bytes.length >= 24 && ascii(bytes, 12, 4) === "IHDR" ? { width: be32(bytes, 16), height: be32(bytes, 20) } : null;
}

function jpegDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  if (bytes.length < 4 || bytes[0] !== 0xff || bytes[1] !== 0xd8) return null;
  let index = 2;
  while (index + 9 <= bytes.length) {
    if (bytes[index] !== 0xff) {
      index += 1;
      continue;
    }
    index += 1;
    while (index < bytes.length && bytes[index] === 0xff) index += 1;
    if (index >= bytes.length) return null;
    const marker = bytes[index]!;
    index += 1;
    if (marker === 0xd9 || marker === 0xda) break;
    if (marker === 0xd8 || (marker >= 0xd0 && marker <= 0xd7)) continue;
    if (index + 2 > bytes.length) return null;
    const length = be16(bytes, index);
    if (length < 2 || index + length > bytes.length) return null;
    if ((marker >= 0xc0 && marker <= 0xc3) || (marker >= 0xc5 && marker <= 0xc7) || (marker >= 0xc9 && marker <= 0xcb) || (marker >= 0xcd && marker <= 0xcf)) {
      return { height: be16(bytes, index + 3), width: be16(bytes, index + 5) };
    }
    index += length;
  }
  return null;
}

function webpDimensions(bytes: Uint8Array): { width: number; height: number } | null {
  if (bytes.length < 30 || ascii(bytes, 0, 4) !== "RIFF" || ascii(bytes, 8, 4) !== "WEBP") return null;
  const chunk = ascii(bytes, 12, 4);
  if (chunk === "VP8X" && bytes.length >= 30) return { width: le24(bytes, 24) + 1, height: le24(bytes, 27) + 1 };
  if (chunk === "VP8 " && bytes.length >= 30) return { width: le16(bytes, 26) & 0x3fff, height: le16(bytes, 28) & 0x3fff };
  if (chunk === "VP8L" && bytes.length >= 25) {
    const value = bytes[21]! | (bytes[22]! << 8) | (bytes[23]! << 16) | (bytes[24]! << 24);
    return { width: (value & 0x3fff) + 1, height: ((value >> 14) & 0x3fff) + 1 };
  }
  return null;
}

function ascii(bytes: Uint8Array, start: number, length: number): string {
  return String.fromCharCode(...bytes.slice(start, start + length));
}

function be16(bytes: Uint8Array, offset: number): number {
  return (bytes[offset]! << 8) | bytes[offset + 1]!;
}

function be32(bytes: Uint8Array, offset: number): number {
  return ((bytes[offset]! << 24) | (bytes[offset + 1]! << 16) | (bytes[offset + 2]! << 8) | bytes[offset + 3]!) >>> 0;
}

function le16(bytes: Uint8Array, offset: number): number {
  return bytes[offset]! | (bytes[offset + 1]! << 8);
}

function le24(bytes: Uint8Array, offset: number): number {
  return bytes[offset]! | (bytes[offset + 1]! << 8) | (bytes[offset + 2]! << 16);
}

function edges(values: number[]): number[] {
  return [...new Set(values.map((value) => Math.round(value * 1000) / 1000))].sort((a, b) => a - b);
}

function styleTransformMatrix(element: Element, style: SvgStyle, viewport: Viewport = defaultViewport(), css: CssRule[] = []): Matrix {
  const matrix = transformMatrix(style.transform);
  const origin = transformOriginPoint(element, style.transformOrigin, viewport, css, style);
  if (!origin) return matrix;
  return multiply(multiply([1, 0, 0, 1, origin[0], origin[1]], matrix), [1, 0, 0, 1, -origin[0], -origin[1]]);
}

function transformMatrix(value: string | null | undefined): Matrix {
  if (!value) return [1, 0, 0, 1, 0, 0];
  if (value.trim().toLowerCase() === "none") return [1, 0, 0, 1, 0, 0];
  let matrix: Matrix = [1, 0, 0, 1, 0, 0];
  for (const match of value.matchAll(/(matrix|translate|scale|rotate|skewx|skewy)\(([^)]*)\)/gi)) {
    const kind = (match[1] || "").toLowerCase();
    const rawArgs = transformArgs(match[2] || "");
    const numbers = rawArgs.map(parseTransformNumberArg);
    const lengths = rawArgs.map(parseTransformLengthArg);
    let next: Matrix = [1, 0, 0, 1, 0, 0];
    if (kind === "matrix" && numbers.length >= 6 && numbers.slice(0, 6).every((item) => item != null)) {
      next = [numbers[0]!, numbers[1]!, numbers[2]!, numbers[3]!, numbers[4]!, numbers[5]!];
    } else if (kind === "translate") {
      next = [1, 0, 0, 1, lengths[0] ?? 0, lengths[1] ?? 0];
    } else if (kind === "scale" && numbers.length > 0) {
      next = [numbers[0] ?? 1, 0, 0, numbers[1] ?? numbers[0] ?? 1, 0, 0];
    } else if (kind === "rotate") {
      const angleDegrees = parseTransformAngleArg(rawArgs[0] || "0") ?? 0;
      const angle = (angleDegrees * Math.PI) / 180;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      if (lengths.length >= 3 && lengths[1] != null && lengths[2] != null) {
        const cx = lengths[1];
        const cy = lengths[2];
        next = multiply(multiply([1, 0, 0, 1, cx, cy], [cos, sin, -sin, cos, 0, 0]), [1, 0, 0, 1, -cx, -cy]);
      } else {
        next = [cos, sin, -sin, cos, 0, 0];
      }
    } else if (kind === "skewx") {
      const angle = ((parseTransformAngleArg(rawArgs[0] || "0") ?? 0) * Math.PI) / 180;
      next = [1, 0, Math.tan(angle), 1, 0, 0];
    } else if (kind === "skewy") {
      const angle = ((parseTransformAngleArg(rawArgs[0] || "0") ?? 0) * Math.PI) / 180;
      next = [1, Math.tan(angle), 0, 1, 0, 0];
    }
    matrix = multiply(matrix, next);
  }
  return matrix;
}

function transformArgs(value: string): string[] {
  return value.replaceAll(",", " ").trim().split(/\s+/).filter(Boolean);
}

function parseTransformNumberArg(value: string): number | null {
  if (/[a-z%]/i.test(value)) return null;
  const number = Number.parseFloat(value);
  return Number.isFinite(number) ? number : null;
}

function parseTransformLengthArg(value: string): number | null {
  const number = parseAbsoluteLength(value);
  return Number.isFinite(number) ? number : null;
}

function parseTransformAngleArg(value: string): number | null {
  const trimmed = value.trim().toLowerCase();
  const number = Number.parseFloat(trimmed);
  if (!Number.isFinite(number)) return null;
  if (trimmed.endsWith("turn")) return number * 360;
  if (trimmed.endsWith("grad")) return number * 0.9;
  if (trimmed.endsWith("rad")) return (number * 180) / Math.PI;
  return number;
}

function transformOriginPoint(element: Element, value: string | null | undefined, viewport: Viewport = defaultViewport(), css: CssRule[] = [], inheritedStyle: SvgStyle = {}): [number, number] | null {
  if (!value) return null;
  const parts = transformOriginParts(value);
  if (!parts) return null;
  const box = elementReferenceBox(element, viewport, css, inheritedStyle);
  const x = originLength(parts[0], "x", box);
  const y = originLength(parts[1], "y", box);
  if (x == null || y == null) return null;
  if (parts[2] != null) {
    const z = parseAbsoluteLength(parts[2]);
    if (!Number.isFinite(z) || Math.abs(z) > 0.000001) return null;
  }
  return [x, y];
}

function transformOriginParts(value: string): [string, string, string?] | null {
  const rawParts = value.trim().split(/\s+/).filter(Boolean);
  if (rawParts.length < 1 || rawParts.length > 3) return null;
  const normalized = rawParts.map((part) => part.toLowerCase());
  const z = rawParts[2];
  const xy = normalized.slice(0, 2);
  let resolved: [string, string];
  if (xy.length === 1) {
    const first = xy[0]!;
    if (first === "left" || first === "right") resolved = [originKeywordToPercent(first), "50%"];
    else if (first === "top" || first === "bottom") resolved = ["50%", originKeywordToPercent(first)];
    else if (first === "center") resolved = ["50%", "50%"];
    else resolved = [rawParts[0]!, "50%"];
  } else {
    const first = xy[0]!;
    const second = xy[1]!;
    const firstAxis = originKeywordAxis(first);
    const secondAxis = originKeywordAxis(second);
    if (firstAxis && firstAxis === secondAxis) return null;
    if (firstAxis === "y" || secondAxis === "x") resolved = [originKeywordToPercent(second), originKeywordToPercent(first)];
    else resolved = [originKeywordToPercent(first), originKeywordToPercent(second)];
  }
  return z == null ? resolved : [resolved[0], resolved[1], z];
}

function originKeywordAxis(value: string): "x" | "y" | null {
  if (value === "left" || value === "right") return "x";
  if (value === "top" || value === "bottom") return "y";
  return null;
}

function originKeywordToPercent(value: string): string {
  return { left: "0%", top: "0%", center: "50%", right: "100%", bottom: "100%" }[value] ?? value;
}

function originLength(value: string, axis: "x" | "y", box: { x: number; y: number; width: number; height: number } | null): number | null {
  const trimmed = value.trim();
  if (trimmed.endsWith("%")) {
    if (!box) return null;
    const percent = Number.parseFloat(trimmed.slice(0, -1));
    if (!Number.isFinite(percent)) return null;
    return (axis === "x" ? box.x : box.y) + ((axis === "x" ? box.width : box.height) * percent) / 100;
  }
  const length = parseAbsoluteLength(trimmed);
  return Number.isFinite(length) ? length : null;
}

function elementReferenceBox(element: Element, viewport: Viewport = defaultViewport(), css: CssRule[] = [], inheritedStyle: SvgStyle = {}): { x: number; y: number; width: number; height: number } | null {
  const tag = localName(element);
  const declarations = resolvedCascadedDeclarations(element, css, inheritedStyle);
  if (tag === "rect" || tag === "image" || tag === "foreignObject") {
    const width = cascadedGeom(element, declarations, "width", "x", viewport);
    const height = cascadedGeom(element, declarations, "height", "y", viewport);
    return width >= 0 && height >= 0 ? { x: cascadedGeom(element, declarations, "x", "x", viewport), y: cascadedGeom(element, declarations, "y", "y", viewport), width, height } : null;
  }
  if (tag === "circle") {
    const r = cascadedGeom(element, declarations, "r", "diag", viewport);
    return r >= 0 ? { x: cascadedGeom(element, declarations, "cx", "x", viewport) - r, y: cascadedGeom(element, declarations, "cy", "y", viewport) - r, width: r * 2, height: r * 2 } : null;
  }
  if (tag === "ellipse") {
    const rx = cascadedGeom(element, declarations, "rx", "x", viewport);
    const ry = cascadedGeom(element, declarations, "ry", "y", viewport);
    return rx >= 0 && ry >= 0 ? { x: cascadedGeom(element, declarations, "cx", "x", viewport) - rx, y: cascadedGeom(element, declarations, "cy", "y", viewport) - ry, width: rx * 2, height: ry * 2 } : null;
  }
  if (tag === "line") {
    const x1 = cascadedGeom(element, declarations, "x1", "x", viewport);
    const y1 = cascadedGeom(element, declarations, "y1", "y", viewport);
    const x2 = cascadedGeom(element, declarations, "x2", "x", viewport);
    const y2 = cascadedGeom(element, declarations, "y2", "y", viewport);
    return { x: Math.min(x1, x2), y: Math.min(y1, y2), width: Math.abs(x2 - x1), height: Math.abs(y2 - y1) };
  }
  const points = tag === "polygon" || tag === "polyline" ? parsePoints(element.getAttribute("points") || "") : tag === "path" ? parseBasicPath(element.getAttribute("d") || "", [1, 0, 0, 1, 0, 0])?.points ?? [] : [];
  if (!points.length) return null;
  const xs = points.map(([x]) => x);
  const ys = points.map(([, y]) => y);
  return { x: Math.min(...xs), y: Math.min(...ys), width: Math.max(...xs) - Math.min(...xs), height: Math.max(...ys) - Math.min(...ys) };
}

function multiply(a: Matrix, b: Matrix): Matrix {
  return [a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1], a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3], a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5]];
}

function point(m: Matrix, x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

function transformedBox(matrix: Matrix, x: number, y: number, width: number, height: number): { x: number; y: number; width: number; height: number } {
  const points = [point(matrix, x, y), point(matrix, x + width, y), point(matrix, x + width, y + height), point(matrix, x, y + height)];
  const xs = points.map(([px]) => px);
  const ys = points.map(([, py]) => py);
  const minX = Math.min(...xs);
  const minY = Math.min(...ys);
  return { x: minX, y: minY, width: Math.max(...xs) - minX, height: Math.max(...ys) - minY };
}

function transformedImageBox(matrix: Matrix, x: number, y: number, width: number, height: number): { x: number; y: number; width: number; height: number; rotation: number | null; flipH: boolean; flipV: boolean } {
  const fallback = transformedBox(matrix, x, y, width, height);
  const corners = [point(matrix, x, y), point(matrix, x + width, y), point(matrix, x + width, y + height), point(matrix, x, y + height)];
  const vx: [number, number] = [corners[1]![0] - corners[0]![0], corners[1]![1] - corners[0]![1]];
  const vy: [number, number] = [corners[3]![0] - corners[0]![0], corners[3]![1] - corners[0]![1]];
  const w = Math.hypot(vx[0], vx[1]);
  const h = Math.hypot(vy[0], vy[1]);
  if (w <= 1e-9 || h <= 1e-9 || Math.abs(vx[0] * vy[0] + vx[1] * vy[1]) > 1e-6 * w * h) {
    return { ...fallback, rotation: null, flipH: false, flipV: false };
  }
  const determinant = vx[0] * vy[1] - vx[1] * vy[0];
  let rotation = (Math.atan2(vx[1], vx[0]) * 180) / Math.PI;
  if (rotation < 0) rotation += 360;
  if (rotation >= 360) rotation -= 360;
  const centerX = corners.reduce((sum, [px]) => sum + px, 0) / 4;
  const centerY = corners.reduce((sum, [, py]) => sum + py, 0) / 4;
  const normalizedRotation = Math.abs(rotation) < 1e-9 || Math.abs(rotation - 360) < 1e-9 ? null : rotation;
  return { x: centerX - w / 2, y: centerY - h / 2, width: w, height: h, rotation: normalizedRotation, flipH: false, flipV: determinant < 0 };
}

function matrixKeepsRectUpright(matrix: Matrix): boolean {
  const [a, b, c, d] = matrix;
  const epsilon = 1e-9;
  return Math.abs(b) < epsilon && Math.abs(c) < epsilon && a > epsilon && d > epsilon;
}

function matrixKeepsRectAxisAligned(matrix: Matrix): boolean {
  const [a, b, c, d] = matrix;
  const epsilon = 1e-9;
  return Math.abs(b) < epsilon && Math.abs(c) < epsilon && Math.abs(a) > epsilon && Math.abs(d) > epsilon;
}

function parsePoints(value: string): [number, number][] {
  const numbers = value.replaceAll(",", " ").trim().split(/\s+/).map(Number).filter((item) => Number.isFinite(item));
  const points: [number, number][] = [];
  for (let index = 0; index + 1 < numbers.length; index += 2) {
    points.push([numbers[index]!, numbers[index + 1]!]);
  }
  return points;
}

function parseBasicPath(value: string, matrix: Matrix): { points: [number, number][]; closed: boolean } | null {
  const tokens = value.match(/[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:(?:\d*\.\d+)|(?:\d+\.?))(?:[eE][-+]?\d+)?/g) || [];
  const points: [number, number][] = [];
  let command = "";
  let index = 0;
  let x = 0;
  let y = 0;
  let start: [number, number] | null = null;
  let lastCubicControl: [number, number] | null = null;
  let lastQuadControl: [number, number] | null = null;
  let closed = false;
  const nextNumber = () => {
    const token = tokens[index++];
    return token == null ? null : Number(token);
  };
  const nextPoint = (relative: boolean): [number, number] | null => {
    const nx = nextNumber();
    const ny = nextNumber();
    if (nx == null || ny == null || !Number.isFinite(nx) || !Number.isFinite(ny)) return null;
    return relative ? [x + nx, y + ny] : [nx, ny];
  };
  const pushPoint = (raw: [number, number]) => {
    const transformed = point(matrix, raw[0], raw[1]);
    if (!start) start = transformed;
    points.push(transformed);
  };
  while (index < tokens.length) {
    const token = tokens[index]!;
    if (/^[A-Za-z]$/.test(token)) {
      command = token;
      index += 1;
    }
    if (!/[MmLlHhVvCcSsQqTtAaZz]/.test(command)) return null;
    if (command === "Z" || command === "z") {
      closed = true;
      if (start) points.push(start);
      continue;
    }
    if (command === "H" || command === "h") {
      const nx = nextNumber();
      if (nx == null) return null;
      x = command === "h" ? x + nx : nx;
      pushPoint([x, y]);
      lastCubicControl = null;
      lastQuadControl = null;
    } else if (command === "V" || command === "v") {
      const ny = nextNumber();
      if (ny == null) return null;
      y = command === "v" ? y + ny : ny;
      pushPoint([x, y]);
      lastCubicControl = null;
      lastQuadControl = null;
    } else if (command === "M" || command === "m" || command === "L" || command === "l") {
      const next = nextPoint(command === "m" || command === "l");
      if (!next) return null;
      [x, y] = next;
      pushPoint([x, y]);
      if (command === "M") command = "L";
      if (command === "m") command = "l";
      lastCubicControl = null;
      lastQuadControl = null;
    } else if (command === "C" || command === "c") {
      const c1 = nextPoint(command === "c");
      const c2 = nextPoint(command === "c");
      const end = nextPoint(command === "c");
      if (!c1 || !c2 || !end) return null;
      for (const curve of cubicPoints([x, y], c1, c2, end)) pushPoint(curve);
      [x, y] = end;
      lastCubicControl = c2;
      lastQuadControl = null;
    } else if (command === "S" || command === "s") {
      const c1: [number, number] = lastCubicControl ? [x * 2 - lastCubicControl[0], y * 2 - lastCubicControl[1]] : [x, y];
      const c2 = nextPoint(command === "s");
      const end = nextPoint(command === "s");
      if (!c2 || !end) return null;
      for (const curve of cubicPoints([x, y], c1, c2, end)) pushPoint(curve);
      [x, y] = end;
      lastCubicControl = c2;
      lastQuadControl = null;
    } else if (command === "Q" || command === "q") {
      const control = nextPoint(command === "q");
      const end = nextPoint(command === "q");
      if (!control || !end) return null;
      for (const curve of quadraticPoints([x, y], control, end)) pushPoint(curve);
      [x, y] = end;
      lastQuadControl = control;
      lastCubicControl = null;
    } else if (command === "T" || command === "t") {
      const control: [number, number] = lastQuadControl ? [x * 2 - lastQuadControl[0], y * 2 - lastQuadControl[1]] : [x, y];
      const end = nextPoint(command === "t");
      if (!end) return null;
      for (const curve of quadraticPoints([x, y], control, end)) pushPoint(curve);
      [x, y] = end;
      lastQuadControl = control;
      lastCubicControl = null;
    } else if (command === "A" || command === "a") {
      const rx = nextNumber();
      const ry = nextNumber();
      const angle = nextNumber();
      const largeArc = nextNumber();
      const sweep = nextNumber();
      const end = nextPoint(command === "a");
      if (rx == null || ry == null || angle == null || largeArc == null || sweep == null || !end) return null;
      for (const arc of arcPoints([x, y], rx, ry, angle, Math.round(largeArc) !== 0, Math.round(sweep) !== 0, end)) pushPoint(arc);
      [x, y] = end;
      lastQuadControl = null;
      lastCubicControl = null;
    }
  }
  return points.length >= 2 ? { points, closed } : null;
}

function cubicPoints(start: [number, number], c1: [number, number], c2: [number, number], end: [number, number]): [number, number][] {
  const points: [number, number][] = [];
  for (let step = 1; step <= 12; step += 1) {
    const t = step / 12;
    const u = 1 - t;
    points.push([
      u ** 3 * start[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * end[0],
      u ** 3 * start[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * end[1],
    ]);
  }
  return points;
}

function quadraticPoints(start: [number, number], control: [number, number], end: [number, number]): [number, number][] {
  const points: [number, number][] = [];
  for (let step = 1; step <= 8; step += 1) {
    const t = step / 8;
    const u = 1 - t;
    points.push([
      u * u * start[0] + 2 * u * t * control[0] + t * t * end[0],
      u * u * start[1] + 2 * u * t * control[1] + t * t * end[1],
    ]);
  }
  return points;
}

function arcPoints(
  start: [number, number],
  rxValue: number,
  ryValue: number,
  xAxisRotation: number,
  largeArc: boolean,
  sweep: boolean,
  end: [number, number],
): [number, number][] {
  if (rxValue === 0 || ryValue === 0 || (start[0] === end[0] && start[1] === end[1])) return [end];
  let rx = Math.abs(rxValue);
  let ry = Math.abs(ryValue);
  const phi = ((xAxisRotation % 360) * Math.PI) / 180;
  const cosPhi = Math.cos(phi);
  const sinPhi = Math.sin(phi);
  const dx = (start[0] - end[0]) / 2;
  const dy = (start[1] - end[1]) / 2;
  const x1p = cosPhi * dx + sinPhi * dy;
  const y1p = -sinPhi * dx + cosPhi * dy;
  const radiusScale = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry);
  if (radiusScale > 1) {
    const scale = Math.sqrt(radiusScale);
    rx *= scale;
    ry *= scale;
  }
  const sign = largeArc === sweep ? -1 : 1;
  const numerator = Math.max(rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p, 0);
  const denominator = rx * rx * y1p * y1p + ry * ry * x1p * x1p;
  const coef = denominator ? sign * Math.sqrt(numerator / denominator) : 0;
  const cxp = coef * ((rx * y1p) / ry);
  const cyp = coef * ((-ry * x1p) / rx);
  const cx = cosPhi * cxp - sinPhi * cyp + (start[0] + end[0]) / 2;
  const cy = sinPhi * cxp + cosPhi * cyp + (start[1] + end[1]) / 2;
  const startAngle = vectorAngle([1, 0], [(x1p - cxp) / rx, (y1p - cyp) / ry]);
  let deltaAngle = vectorAngle([(x1p - cxp) / rx, (y1p - cyp) / ry], [(-x1p - cxp) / rx, (-y1p - cyp) / ry]);
  if (!sweep && deltaAngle > 0) deltaAngle -= Math.PI * 2;
  if (sweep && deltaAngle < 0) deltaAngle += Math.PI * 2;
  const segments = Math.max(4, Math.min(32, Math.ceil(Math.abs(deltaAngle) / (Math.PI / 12))));
  const points: [number, number][] = [];
  for (let step = 1; step <= segments; step += 1) {
    const theta = startAngle + (deltaAngle * step) / segments;
    points.push([
      cosPhi * rx * Math.cos(theta) - sinPhi * ry * Math.sin(theta) + cx,
      sinPhi * rx * Math.cos(theta) + cosPhi * ry * Math.sin(theta) + cy,
    ]);
  }
  return points;
}

function vectorAngle(u: [number, number], v: [number, number]): number {
  return Math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]);
}

function emu(value: number): number {
  return Math.round(value * emuPerPx);
}

function hex(value: string): string {
  const parsed = parseCssColor(value);
  if (parsed) return parsed.slice(1, 7).toUpperCase();
  if (value.startsWith("#")) {
    const raw = value.slice(1);
    if (raw.length === 3) return raw.split("").map((char) => char + char).join("").toUpperCase();
    return raw.slice(0, 6).toUpperCase();
  }
  return "111827";
}

function xml(value: string): string {
  return escapeHtml(value);
}

function xmlDecl(body: string): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>${body}`;
}

const nsA = "http://schemas.openxmlformats.org/drawingml/2006/main";
const nsP = "http://schemas.openxmlformats.org/presentationml/2006/main";
const nsR = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";

function contentTypes(slideCount: number, masterCount = 1, layoutCount = 1, hasCustomXml = false, hasOfficeCausal = false): string {
  const masters = Array.from({ length: masterCount }, (_, index) => `  <Override PartName="/ppt/slideMasters/slideMaster${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>`).join("\n");
  const layouts = Array.from({ length: layoutCount }, (_, index) => `  <Override PartName="/ppt/slideLayouts/slideLayout${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>`).join("\n");
  const slides = Array.from({ length: slideCount }, (_, index) => `  <Override PartName="/ppt/slides/slide${index + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>`).join("\n");
  const customXml = hasCustomXml ? '<Override PartName="/customXml/item1.xml" ContentType="application/xml"/>' : "";
  const officeCausal = hasOfficeCausal ? '<Default Extension="jsonl" ContentType="application/jsonl"/>' : "";
  return xmlDecl(`<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>${officeCausal}<Default Extension="png" ContentType="image/png"/><Default Extension="jpg" ContentType="image/jpeg"/><Default Extension="gif" ContentType="image/gif"/><Default Extension="webp" ContentType="image/webp"/><Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/><Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>${masters}${layouts}<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>${slides}${customXml}</Types>`);
}

function appProps(slideCount: number): string {
  return xmlDecl(`<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>SVGraph web</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>${slideCount}</Slides></Properties>`);
}

function presentationXml(slideCount: number, [width, height]: [number, number], masterCount = 1): string {
  const masterIds = Array.from({ length: masterCount }, (_, index) => `<p:sldMasterId id="${2147483648 + index}" r:id="rId${index + 1}"/>`).join("");
  const ids = Array.from({ length: slideCount }, (_, index) => `<p:sldId id="${256 + index}" r:id="rId${masterCount + index + 1}"/>`).join("");
  return xmlDecl(`<p:presentation xmlns:a="${nsA}" xmlns:r="${nsR}" xmlns:p="${nsP}"><p:sldMasterIdLst>${masterIds}</p:sldMasterIdLst><p:sldIdLst>${ids}</p:sldIdLst><p:sldSz cx="${emu(width)}" cy="${emu(height)}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>`);
}

function presentationRels(slideCount: number, masterCount = 1): string {
  const masters = Array.from({ length: masterCount }, (_, index) => `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster${index + 1}.xml"/>`).join("");
  const slides = Array.from({ length: slideCount }, (_, index) => `<Relationship Id="rId${masterCount + index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide${index + 1}.xml"/>`).join("");
  return xmlDecl(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${masters}${slides}<Relationship Id="rId${masterCount + slideCount + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="theme/theme1.xml"/></Relationships>`);
}

function rootRels(hasCustomXml = false, hasOfficeCausal = false): string {
  const customXml = hasCustomXml ? '<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/customXml" Target="customXml/item1.xml"/>' : "";
  const officeCausal = hasOfficeCausal ? '<Relationship Id="rIdOfficeCasual" Type="https://com-junkawasaki.org/office-causal/relationship" Target="ocz/causal.jsonl"/>' : "";
  return xmlDecl(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>${customXml}${officeCausal}</Relationships>`);
}

function svgraphPresentationSidecar(presentation: SVGraphPresentationProjection, sourceSvg: string): string {
  const payload = xml(JSON.stringify({ ...presentation, source_svg: sourceSvg }));
  return xmlDecl(`<svgraph:presentation xmlns:svgraph="https://com-junkawasaki.github.io/svgraph/schema/presentation" version="1"><svgraph:json>${payload}</svgraph:json></svgraph:presentation>`);
}
const coreProps = xmlDecl(`<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>SVGraph web export</dc:title><dc:creator>SVGraph web</dc:creator><cp:lastModifiedBy>SVGraph web</cp:lastModifiedBy></cp:coreProperties>`);
function slideLayoutRel(layoutIndex = 1): string {
  return `<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout${layoutIndex}.xml"/>`;
}

function slideMasterRels(layoutIndex = 1): string {
  return xmlDecl(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout${layoutIndex}.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>`);
}

function slideLayoutRels(masterIndex = 1): string {
  return xmlDecl(`<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster${masterIndex}.xml"/></Relationships>`);
}
function slideMaster(textStyles: TextStyleRecord[] = []): string {
  const titleStyle = textStyleXml("titleStyle", textStyleForRole(textStyles, "title"));
  const bodyStyle = textStyleXml("bodyStyle", textStyleForRole(textStyles, "body"));
  const otherStyle = textStyleXml(
    "otherStyle",
    textStyleForRole(textStyles, "other") || textStyleForRole(textStyles, "lead") || textStyleForRole(textStyles, "caption"),
  );
  return xmlDecl(`<p:sldMaster xmlns:a="${nsA}" xmlns:r="${nsR}" xmlns:p="${nsP}"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/><p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles>${titleStyle}${bodyStyle}${otherStyle}</p:txStyles></p:sldMaster>`);
}

function textStyleForRole(textStyles: TextStyleRecord[], role: string): TextStyleRecord | null {
  const normalized = role.toLowerCase();
  return textStyles.find((style) => style.role.toLowerCase() === normalized) ?? null;
}

function textStyleXml(tag: string, style: TextStyleRecord | null): string {
  if (!style) return `<p:${tag}/>`;
  const properties = style.properties as Record<string, JsonValue>;
  const attrs: string[] = [];
  const fontSize = styleNumber(properties.fontSize ?? properties["font-size"]);
  if (fontSize != null) attrs.push(`sz="${Math.round(fontSize * 100)}"`);
  if (styleBool(properties.bold ?? properties.fontWeight ?? properties["font-weight"])) attrs.push('b="1"');
  if (styleBool(properties.italic ?? properties.fontStyle ?? properties["font-style"])) attrs.push('i="1"');
  const fontFamily = properties.fontFamily ?? properties["font-family"];
  const latin = typeof fontFamily === "string" ? `<a:latin typeface="${xmlAttr(fontFamily)}"/>` : "";
  const attrsText = attrs.length ? ` ${attrs.join(" ")}` : "";
  return `<p:${tag}><a:lvl1pPr><a:defRPr${attrsText}>${latin}</a:defRPr></a:lvl1pPr></p:${tag}>`;
}

function styleNumber(value: JsonValue | undefined): number | null {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const match = value.match(/^\s*([0-9]+(?:\.[0-9]+)?)/);
    return match ? Number(match[1]) : null;
  }
  return null;
}

function styleBool(value: JsonValue | undefined): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value >= 600;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    return ["1", "true", "bold", "bolder"].includes(normalized) || (/^\d+$/.test(normalized) && Number(normalized) >= 600);
  }
  return false;
}

function xmlAttr(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}
const slideLayout = xmlDecl(`<p:sldLayout xmlns:a="${nsA}" xmlns:r="${nsR}" xmlns:p="${nsP}" type="blank" preserve="1"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>`);
const themeXml = xmlDecl(`<a:theme xmlns:a="${nsA}" name="SVGraph web"><a:themeElements><a:clrScheme name="SVGraph"><a:dk1><a:srgbClr val="111827"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="1F2937"/></a:dk2><a:lt2><a:srgbClr val="F9FAFB"/></a:lt2><a:accent1><a:srgbClr val="1D4ED8"/></a:accent1><a:accent2><a:srgbClr val="15803D"/></a:accent2><a:accent3><a:srgbClr val="DC2626"/></a:accent3><a:accent4><a:srgbClr val="7C3AED"/></a:accent4><a:accent5><a:srgbClr val="0891B2"/></a:accent5><a:accent6><a:srgbClr val="EA580C"/></a:accent6><a:hlink><a:srgbClr val="2563EB"/></a:hlink><a:folHlink><a:srgbClr val="9333EA"/></a:folHlink></a:clrScheme><a:fontScheme name="SVGraph"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme><a:fmtScheme name="SVGraph"><a:fillStyleLst/><a:lnStyleLst/><a:effectStyleLst/><a:bgFillStyleLst/></a:fmtScheme></a:themeElements></a:theme>`);
