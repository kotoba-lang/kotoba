export interface CreateDmnViewerOptions {
  container: HTMLElement;
}

export interface DmnViewerHandle {
  importXML: (xml: string) => Promise<void>;
  destroy: () => void;
}

