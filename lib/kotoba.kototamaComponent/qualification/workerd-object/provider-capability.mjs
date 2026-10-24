const operations = Object.freeze({
  "identity-sign": "identity/sign",
  "identity-verify": "identity/verify",
  "hash-sha256": "hash/sha256",
  "http-post": "http/post",
  "log-read": "log/read",
  "object-get-stream": "object/get-stream",
  "object-put-block": "object/put-block",
  "object-compare-and-set-ref": "object/compare-and-set-ref",
});
const issued = new Set();

export class Grant {
  constructor(operation) {
    if (!Object.values(operations).includes(operation) || issued.has(operation)) {
      throw "quota";
    }
    this.operation = operation;
    issued.add(operation);
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
  const operation = operations[request];
  if (!operation) throw "provider-failed";
  return new Grant(operation);
}
