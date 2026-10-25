// Type declarations for external modules (same as compiler)

declare module 'bpmn-moddle' {
  export interface ModdleElement {
    $type: string;
    id?: string;
    name?: string;
    [key: string]: any;
  }

  export class BpmnModdle {
    constructor(packages?: any[]);
    create(type: string, attrs?: any): ModdleElement;
  }

  export default BpmnModdle;
}

declare module 'moddle-xml' {
  export interface FromXMLResult {
    rootElement: any;
    warnings?: any[];
  }

  export function fromXML(xml: string, options?: any): Promise<FromXMLResult>;
}
