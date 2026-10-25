import { getSchemaVariables as jsGetSchemaVariables } from "@bpmn-io/form-js";
import type { FormSchema } from "../types.js";

export interface SchemaVariableOptions {
  inputs?: boolean;
  outputs?: boolean;
}

export interface SchemaVariablesResult {
  inputs: string[];
  outputs: string[];
}

export function getSchemaVariables(schema: FormSchema, opts?: SchemaVariableOptions): SchemaVariablesResult | string[] {
  const variables = jsGetSchemaVariables(schema as any, opts as any);
  // form-js may return either an array or object depending on options
  return variables as any;
}

