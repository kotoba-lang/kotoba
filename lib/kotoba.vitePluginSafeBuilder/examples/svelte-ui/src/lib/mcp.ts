type Tool = { name?: string; description?: string };

export async function listTools(): Promise<Tool[]> {
  const res = await fetch('/xrpc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: '1', method: 'tools/list', params: {} }),
  });
  const data = await res.json();
  return data.result?.tools ?? [];
}

export async function runTool(name: string, args: Record<string, unknown>): Promise<unknown> {
  const res = await fetch('/xrpc', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: '1', method: 'tools/call', params: { name, arguments: args } }),
  });
  const data = await res.json();
  if (data.error) throw new Error(data.error.message ?? 'tool call failed');
  return data.result;
}
