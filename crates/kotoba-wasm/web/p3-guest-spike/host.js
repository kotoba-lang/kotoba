export default function hostGet(key) {
  // In the browser this calls back into the KotobaNode (kqe read, etc.).
  return `kotoba-host[${key}]`;
}
