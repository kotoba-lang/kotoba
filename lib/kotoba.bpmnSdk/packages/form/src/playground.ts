import { assertClient } from "./ssr.js";
import { FormPlayground as JsFormPlayground } from "@bpmn-io/form-js";
import type { PlaygroundOptions, FormPlaygroundHandle } from "./types.js";

export async function createFormPlayground(options: PlaygroundOptions): Promise<FormPlaygroundHandle> {
  assertClient();

  const playground = new JsFormPlayground({
    container: options.container,
    schema: options.schema as any,
    data: options.data as any,
  });

  const handle: FormPlaygroundHandle = {
    destroy: () => {
      playground.destroy();
    },
  };

  return handle;
}

