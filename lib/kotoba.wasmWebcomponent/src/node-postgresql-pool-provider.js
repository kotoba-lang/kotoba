const encoder = new TextEncoder();

function bytes(memory, ptr, len) {
  if (!Number.isInteger(ptr) || !Number.isInteger(len) || ptr < 0 || len <= 0 || ptr + len > memory.buffer.byteLength || len > 255) return null;
  return new Uint8Array(memory.buffer, ptr, len).slice();
}

function copy(fromMemory, from, toMemory, to, len) {
  const value = new Uint8Array(fromMemory.buffer, from, len).slice();
  new Uint8Array(toMemory.buffer, to, len).set(value);
}

function callRaw(instance, name, args) {
  const fn = instance?.exports?.[name];
  if (typeof fn !== 'function') throw new Error(`PostgreSQL pool dependency lacks ${name}`);
  return fn(...args);
}

function call(instance, name, args) {
  return Number(callRaw(instance, name, args));
}

export function createNodePostgresqlPoolProvider({
  scramInstance, queryInstance, maxPools = 4, maxLeases = 16,
  maxConnectionsPerPool = 4, idleTimeoutMs = 30_000,
  maxLifetimeMs = 300_000, now = () => Date.now(),
} = {}) {
  if (!scramInstance?.exports?.memory || !queryInstance?.exports?.memory ||
      !Number.isInteger(maxPools) || maxPools < 1 || !Number.isInteger(maxLeases) || maxLeases < 1 ||
      !Number.isInteger(maxConnectionsPerPool) || maxConnectionsPerPool < 1 || maxConnectionsPerPool > maxLeases ||
      !Number.isFinite(idleTimeoutMs) || idleTimeoutMs < 0 || !Number.isFinite(maxLifetimeMs) || maxLifetimeMs <= 0) {
    throw new Error('invalid PostgreSQL pool bounds or component dependencies');
  }
  const memory = new WebAssembly.Memory({ initial: 1 });
  const scramBase = scramInstance.exports.memory.grow(1) * 65536;
  let nextPool = 1, nextConnection = 1, nextLease = 1;
  const pools = new Map(), leases = new Map();

  function closeConnection(connection) {
    if (!connection.closed) call(scramInstance, 'pg-close-scram', [connection.channel]);
    connection.closed = true;
  }

  function expired(connection) {
    const age = now() - connection.createdAt;
    const idle = now() - connection.lastUsedAt;
    return connection.status === 'idle' && (age >= maxLifetimeMs || (idleTimeoutMs > 0 && idle >= idleTimeoutMs));
  }

  function reap(pool) {
    for (const [id, connection] of pool.connections) if (expired(connection)) {
      closeConnection(connection); pool.connections.delete(id); pool.metrics.evictions++;
    }
  }

  function openConnection(pool) {
    if (pool.connections.size >= maxConnectionsPerPool) return null;
    const values = [pool.host, pool.user, pool.database, pool.credential];
    const offsets = [scramBase, scramBase + 256, scramBase + 512, scramBase + 768];
    values.forEach((value, i) => new Uint8Array(scramInstance.exports.memory.buffer, offsets[i], value.length).set(value));
    const channel = callRaw(scramInstance, 'pg-open-scram-random', [offsets[0], values[0].length, pool.port,
      offsets[1], values[1].length, offsets[2], values[2].length, offsets[3], values[3].length]);
    if (channel < 0) return null;
    const base = queryInstance.exports.memory.grow(1) * 65536;
    const connection = { id: nextConnection++, channel, base, status: 'idle', createdAt: now(), lastUsedAt: now(), closed: false };
    pool.connections.set(connection.id, connection); pool.metrics.connectionsCreated++;
    return connection;
  }

  function connectionForLease(leaseId) {
    const lease = leases.get(leaseId), pool = lease && pools.get(lease.poolId);
    const connection = pool?.connections.get(lease?.connectionId);
    return lease && connection?.status === 'leased' ? { lease, pool, connection } : null;
  }

  function query(connection, queryPtr, queryLen, outPtr, outCap, metaPtr, metaCap) {
    if (queryLen <= 0 || queryLen > 255 || outCap < 0 || outCap > 32768 || metaCap < 7) return -1;
    const base = connection.base, queryBase = base, resultBase = base + 1024, metaBase = base + 50000;
    copy(memory, queryPtr, queryInstance.exports.memory, queryBase, queryLen);
    const n = call(queryInstance, 'pg-query-state', [connection.channel, queryBase, queryLen, resultBase, outCap, metaBase, metaCap]);
    if (n > 0) {
      copy(queryInstance.exports.memory, resultBase, memory, outPtr, n);
      copy(queryInstance.exports.memory, metaBase, memory, metaPtr, 7);
    }
    return n;
  }

  const exports = {
    memory,
    'pg-pool-open': (hostPtr, hostLen, port, userPtr, userLen, dbPtr, dbLen, credentialPtr, credentialLen) => {
      const host = bytes(memory, hostPtr, hostLen), user = bytes(memory, userPtr, userLen);
      const database = bytes(memory, dbPtr, dbLen), credential = bytes(memory, credentialPtr, credentialLen);
      if (!host || !user || !database || !credential || pools.size >= maxPools) return -1;
      const id = nextPool++, pool = { id, host, port, user, database, credential, status: 'open', connections: new Map(),
        metrics: { acquires: 0, timeouts: 0, evictions: 0, connectionsCreated: 0 } };
      pools.set(id, pool);
      if (!openConnection(pool)) { pools.delete(id); return -1; }
      return id;
    },
    'pg-pool-acquire': poolId => {
      const pool = pools.get(poolId); if (!pool || pool.status !== 'open') return -1;
      reap(pool); if (leases.size >= maxLeases) { pool.metrics.timeouts++; return -1; }
      const connection = [...pool.connections.values()].find(item => item.status === 'idle') || openConnection(pool);
      if (!connection) { pool.metrics.timeouts++; return -1; }
      connection.status = 'leased'; const id = nextLease++;
      leases.set(id, { id, poolId, connectionId: connection.id }); pool.metrics.acquires++;
      return id;
    },
    'pg-pool-query': (leaseId, queryPtr, queryLen, outPtr, outCap, metaPtr, metaCap) => {
      const found = connectionForLease(leaseId);
      return found ? query(found.connection, queryPtr, queryLen, outPtr, outCap, metaPtr, metaCap) : -1;
    },
    'pg-pool-release': leaseId => {
      const found = connectionForLease(leaseId); if (!found) return -1;
      leases.delete(leaseId);
      const { pool, connection } = found, base = connection.base;
      const reset = call(queryInstance, 'pg-session-reset', [connection.channel, base + 1024, 32768, base + 50000, 7]);
      if (reset > 0) { connection.status = 'idle'; connection.lastUsedAt = now(); return 0; }
      closeConnection(connection); pool.connections.delete(connection.id); pool.metrics.evictions++; return -1;
    },
    'pg-pool-stats': (poolId, outPtr, cap) => {
      const pool = pools.get(poolId); if (!pool || cap < 32 || outPtr < 0 || outPtr + 32 > memory.buffer.byteLength) return -1;
      const connections = [...pool.connections.values()], view = new DataView(memory.buffer, outPtr, 32);
      const values = [pool.status === 'open' ? 1 : 2, connections.length,
        connections.filter(x => x.status === 'idle').length, connections.filter(x => x.status === 'leased').length,
        0, pool.metrics.acquires, pool.metrics.timeouts, pool.metrics.evictions];
      values.forEach((value, i) => view.setInt32(i * 4, value)); return 32;
    },
    'pg-pool-health': poolId => {
      const pool = pools.get(poolId); if (!pool) return -1; reap(pool); let healthy = 0;
      for (const connection of [...pool.connections.values()]) if (connection.status === 'idle') {
        new Uint8Array(queryInstance.exports.memory.buffer, connection.base, 8).set(encoder.encode('select 1'));
        const n = call(queryInstance, 'pg-query-state', [connection.channel, connection.base, 8,
          connection.base + 1024, 32768, connection.base + 50000, 7]);
        if (n > 0) { connection.lastUsedAt = now(); healthy++; }
        else { closeConnection(connection); pool.connections.delete(connection.id); pool.metrics.evictions++; }
      }
      return healthy;
    },
    'pg-pool-drain': poolId => {
      const pool = pools.get(poolId); if (!pool) return -1; pool.status = 'draining';
      const forced = [...pool.connections.values()].filter(x => x.status === 'leased').length;
      for (const connection of pool.connections.values()) closeConnection(connection);
      for (const [id, lease] of leases) if (lease.poolId === poolId) leases.delete(id);
      pools.delete(poolId); return forced;
    },
    'pg-pool-close': poolId => {
      const pool = pools.get(poolId); if (!pool || [...leases.values()].some(x => x.poolId === poolId)) return -1;
      for (const connection of pool.connections.values()) closeConnection(connection);
      pools.delete(poolId); return 0;
    },
  };
  return { instance: { exports }, closeAll() { for (const pool of pools.values()) for (const connection of pool.connections.values()) closeConnection(connection); pools.clear(); leases.clear(); },
    snapshot: () => ({ pools: pools.size, leases: leases.size }) };
}
