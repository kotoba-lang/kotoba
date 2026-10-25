import { createForm } from "@etzhayyim/bpmn-sdk-form";

const container = document.getElementById("app")!;

const schema = { components: [] } as any;

void (async () => {
  const form = await createForm({ container, schema });
  form.onSubmit((e) => {
    console.log("submitted", e);
  });
})();

