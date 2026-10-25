// Type declarations for external modules

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
  export interface ToXMLResult {
    xml: string;
  }

  export class Writer {
    toXML(element: any, options: any, callback: (err: any, xml: string) => void): void;
  }

  export function fromXML(xml: string, moddle: any): Promise<any>;
  export function toXML(element: any, options?: any): Promise<ToXMLResult>;
}
