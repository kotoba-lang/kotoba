import { assertClient } from "./ssr.js";
import { Form as JsForm } from "@bpmn-io/form-js";
import type { FormHandle, ViewerOptions, FormSchema, FormData, SubmitHandler } from "./types.js";

export async function createForm(options: ViewerOptions): Promise<FormHandle> {
  assertClient();

  const form = new JsForm({ container: options.container });

  await form.importSchema(options.schema as any, options.data as any);

  const handle: FormHandle = {
    importSchema: async (schema, data) => {
      await form.importSchema(schema as any, data as any);
    },
    onSubmit: (cb: SubmitHandler) => {
      form.on("submit", (event: any) => cb({ data: event.data, errors: event.errors ?? [] }));
    },
    destroy: () => {
      form.destroy();
    },
  };

  return handle;
}

