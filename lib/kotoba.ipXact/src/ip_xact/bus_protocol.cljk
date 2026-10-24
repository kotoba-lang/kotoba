(ns ip-xact.bus-protocol
  "Bus protocol signal definitions and RTL generation (AXI4, APB).
  Restored from kami-ip's `bus_protocol` module (deleted PR #82).")

(defn axi-config [addr-width data-width id-width user-width]
  {:addr-width addr-width :data-width data-width :id-width id-width :user-width user-width})

(defn apb-config [addr-width data-width] {:addr-width addr-width :data-width data-width})

(def axi4-signals
  ["AWVALID" "AWREADY" "AWADDR" "AWLEN" "AWSIZE" "AWBURST" "AWID" "AWLOCK" "AWCACHE" "AWPROT" "AWQOS"
   "WVALID" "WREADY" "WDATA" "WSTRB" "WLAST"
   "BVALID" "BREADY" "BRESP" "BID"
   "ARVALID" "ARREADY" "ARADDR" "ARLEN" "ARSIZE" "ARBURST" "ARID" "ARLOCK" "ARCACHE" "ARPROT" "ARQOS"
   "RVALID" "RREADY" "RDATA" "RRESP" "RLAST" "RID"])

(defn generate-axi4-master
  "Generate a Verilog AXI4 master port list from `config`."
  [config]
  (let [{:keys [addr-width data-width id-width]} config
        strb-width (quot data-width 8)]
    (str "// AXI4 Master — addr=" addr-width ", data=" data-width ", id=" id-width "\n"
         "module axi4_master (\n"
         "  input  wire        ACLK,\n"
         "  input  wire        ARESETn,\n"
         "  output wire [" (dec addr-width) ":0] AWADDR,\n"
         "  output wire [" (dec id-width) ":0] AWID,\n"
         "  output wire [7:0]  AWLEN,\n"
         "  output wire [2:0]  AWSIZE,\n"
         "  output wire [1:0]  AWBURST,\n"
         "  output wire        AWVALID,\n"
         "  input  wire        AWREADY,\n"
         "  output wire [" (dec data-width) ":0] WDATA,\n"
         "  output wire [" (dec strb-width) ":0] WSTRB,\n"
         "  output wire        WLAST,\n"
         "  output wire        WVALID,\n"
         "  input  wire        WREADY,\n"
         "  input  wire [1:0]  BRESP,\n"
         "  input  wire [" (dec id-width) ":0] BID,\n"
         "  input  wire        BVALID,\n"
         "  output wire        BREADY,\n"
         "  output wire [" (dec addr-width) ":0] ARADDR,\n"
         "  output wire [" (dec id-width) ":0] ARID,\n"
         "  output wire [7:0]  ARLEN,\n"
         "  output wire [2:0]  ARSIZE,\n"
         "  output wire [1:0]  ARBURST,\n"
         "  output wire        ARVALID,\n"
         "  input  wire        ARREADY,\n"
         "  input  wire [" (dec data-width) ":0] RDATA,\n"
         "  input  wire [1:0]  RRESP,\n"
         "  input  wire        RLAST,\n"
         "  input  wire [" (dec id-width) ":0] RID,\n"
         "  input  wire        RVALID,\n"
         "  output wire        RREADY\n"
         ");\n"
         "  // Master logic placeholder\n"
         "endmodule\n")))

(defn generate-axi4-slave
  "Generate a Verilog AXI4 slave port list from `config`."
  [config]
  (let [{:keys [addr-width data-width id-width]} config
        strb-width (quot data-width 8)]
    (str "// AXI4 Slave — addr=" addr-width ", data=" data-width ", id=" id-width "\n"
         "module axi4_slave (\n"
         "  input  wire        ACLK,\n"
         "  input  wire        ARESETn,\n"
         "  input  wire [" (dec addr-width) ":0] AWADDR,\n"
         "  input  wire [" (dec id-width) ":0] AWID,\n"
         "  input  wire [7:0]  AWLEN,\n"
         "  input  wire [2:0]  AWSIZE,\n"
         "  input  wire [1:0]  AWBURST,\n"
         "  input  wire        AWVALID,\n"
         "  output wire        AWREADY,\n"
         "  input  wire [" (dec data-width) ":0] WDATA,\n"
         "  input  wire [" (dec strb-width) ":0] WSTRB,\n"
         "  input  wire        WLAST,\n"
         "  input  wire        WVALID,\n"
         "  output wire        WREADY,\n"
         "  output wire [1:0]  BRESP,\n"
         "  output wire [" (dec id-width) ":0] BID,\n"
         "  output wire        BVALID,\n"
         "  input  wire        BREADY,\n"
         "  input  wire [" (dec addr-width) ":0] ARADDR,\n"
         "  input  wire [" (dec id-width) ":0] ARID,\n"
         "  input  wire [7:0]  ARLEN,\n"
         "  input  wire [2:0]  ARSIZE,\n"
         "  input  wire [1:0]  ARBURST,\n"
         "  input  wire        ARVALID,\n"
         "  output wire        ARREADY,\n"
         "  output wire [" (dec data-width) ":0] RDATA,\n"
         "  output wire [1:0]  RRESP,\n"
         "  output wire        RLAST,\n"
         "  output wire [" (dec id-width) ":0] RID,\n"
         "  output wire        RVALID,\n"
         "  input  wire        RREADY\n"
         ");\n"
         "  // Slave logic placeholder\n"
         "endmodule\n")))
