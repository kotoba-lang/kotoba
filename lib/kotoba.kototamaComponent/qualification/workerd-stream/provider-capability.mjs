const admittedOperation = "http/get-stream";
let issued = false;

export class Grant {
  constructor(operation) {
    if (operation !== admittedOperation || issued) throw "quota";
    this.operation = operation;
    issued = true;
  }
}

export class BytesStream {
  constructor(bytes) {
    this.bytes = bytes;
    this.offset = 0;
    this.cancelled = false;
  }

  read(maxBytes) {
    if (this.cancelled || !Number.isSafeInteger(maxBytes) || maxBytes <= 0) {
      throw "provider-failed";
    }
    const end = Math.min(this.offset + maxBytes, this.bytes.byteLength);
    const bytes = this.bytes.slice(this.offset, end);
    this.offset = end;
    return { bytes, done: this.offset === this.bytes.byteLength };
  }

  cancel() {
    this.cancelled = true;
  }
}

export class BytesTask {
  constructor(bytes) {
    this.bytes = bytes;
    this.cancelled = false;
    this.polled = false;
  }

  poll() {
    if (this.cancelled || this.polled) throw "provider-failed";
    this.polled = true;
    return { tag: "ready", val: new BytesStream(this.bytes) };
  }

  cancel() {
    this.cancelled = true;
  }
}

export function acquire(request) {
  if (request !== "http-get-stream") throw "provider-failed";
  return new Grant(admittedOperation);
}
