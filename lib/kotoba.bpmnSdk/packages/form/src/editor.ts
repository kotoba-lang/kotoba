import { assertClient } from "./ssr.js";
import { FormEditor as JsFormEditor } from "@bpmn-io/form-js";
import type { EditorOptions, FormEditorHandle } from "./types.js";

export async function createFormEditor(options: EditorOptions): Promise<FormEditorHandle> {
  assertClient();

  const editor = new JsFormEditor({ container: options.container });
  await editor.importSchema(options.schema as any);

  const handle: FormEditorHandle = {
    importSchema: async (schema) => {
      await editor.importSchema(schema as any);
    },
    destroy: () => {
      editor.destroy();
    },
  };

  return handle;
}

