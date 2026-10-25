"use strict";
// Merkle DAG: dsl_package_index
// @etzhayyim/bpmn-sdk-dsl のメインエクスポート
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __exportStar = (this && this.__exportStar) || function(m, exports) {
    for (var p in m) if (p !== "default" && !Object.prototype.hasOwnProperty.call(exports, p)) __createBinding(exports, m, p);
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.flow = void 0;
var bpmn_dsl_1 = require("./bpmn-dsl");
Object.defineProperty(exports, "flow", { enumerable: true, get: function () { return bpmn_dsl_1.flow; } });
// Builders
__exportStar(require("./builders/events"), exports);
__exportStar(require("./builders/tasks"), exports);
__exportStar(require("./builders/gateways"), exports);
__exportStar(require("./builders/subprocess"), exports);
//# sourceMappingURL=index.js.map