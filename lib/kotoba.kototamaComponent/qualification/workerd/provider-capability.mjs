const admittedOperation = "log/append";
let issued = false;

export class Grant {
  constructor(operation) {
    if (operation !== admittedOperation || issued) throw "quota";
    this.operation = operation;
    issued = true;
  }
}

export function acquire(request) {
  if (request !== "log-append") throw "provider-failed";
  return new Grant(admittedOperation);
}
