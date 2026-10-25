// Minimal shape aligned with form-js schema
export type FormSchema = Record<string, unknown>;
export type FormData = Record<string, unknown>;

export interface CreateBaseOptions {
  container: HTMLElement;
}

export interface ViewerOptions extends CreateBaseOptions {
  schema: FormSchema;
  data?: FormData;
}

export interface EditorOptions extends CreateBaseOptions {
  schema: FormSchema;
}

export interface PlaygroundOptions extends CreateBaseOptions {
  schema: FormSchema;
  data?: FormData;
}

export type SubmitHandler = (event: { data: FormData; errors: unknown[] }) => void;

export interface FormHandle {
  importSchema: (schema: FormSchema, data?: FormData) => Promise<void>;
  onSubmit: (cb: SubmitHandler) => void;
  destroy: () => void;
}

export interface FormEditorHandle {
  importSchema: (schema: FormSchema) => Promise<void>;
  destroy: () => void;
}

export interface FormPlaygroundHandle {
  destroy: () => void;
}

