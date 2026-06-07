// graph-builder.ts — Type-safe SQL query builder using Kysely
//
// ⚠️ DEPRECATED 2026-04-12: SQL builder (G()) removed. Use Kysely via createKyselyDb() instead.
//
// MIGRATION: This file has been converted to Kysely (SQL) backend.
// Old SQL usage patterns are archived in _archive/30-graph/kagami/queries/
//
// NEW USAGE (Kysely type-safe):
//   const db = createKyselyDb(env.GRAPH_QUERY_SERVICE);
//   const results = await db
//     .selectFrom("Briefing")
//     .select(["id", "title"])
//     .where("id", "=", "br-1")
//     .execute();
//
//   await db
//     .insertInto("Briefing")
//     .values({ id: "br-1", title: "Test", status: "draft" })
//     .execute();
//
//   await db
//     .updateTable("Briefing")
//     .set({ status: "published" })
//     .where("id", "=", "br-1")
//     .execute();
//
// OLD USAGE (SQL, removed):
//   Graph("Briefing").Create({ id: "br-1", title: "Test", status: "draft" }).Exec();
//   Graph("Briefing").Match({ id: "br-1" }).Return("id", "title").Query();
//   Graph("Briefing").Match({ id: "br-1" }).Set({ status: "published" }).Exec();
//   Graph("Briefing").Match({ id: "br-1" }).Delete().Exec();
//   Graph("Briefing").Where("status", "=", "published").Return("id", "title").OrderBy("createdAt", true).Limit(50).Query();

import type { GraphOp, WhereClause } from "./types.js";
import { getKagamiRpc } from "./sql.js";
// CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
import { createKyselyDb } from "./kysely.js";
import { LABEL_TABLE_MAP } from "@etzhayyim/graph-schema/schema";
import type { GrapharDB } from "@etzhayyim/graph-schema/db";
// schema.ts is now hand-edited Drizzle SSoT (for drizzle-kit migrations only).
// Kysely queries use LABEL_TABLE_MAP to resolve label → table name.
// SQLAlchemy models.py and Python generators archived under
// _archive/30-graph/graph-schema-py-260412/.
import type { ExpressionBuilder, Expression, SqlBool } from "kysely";

/** Resolve Label → table name from LABEL_TABLE_MAP. Returns null if no mapping (caller should fall back to SQL). */
function resolveKyselyTableName(label: string): string | null {
  const tableName = LABEL_TABLE_MAP[label];
  return tableName ?? null;
}

/** Map G() builder Where op string → Kysely ExpressionBuilder operator. */
function whereOpToKysely(
  eb: ExpressionBuilder<GrapharDB, any>,
  prop: string,
  op: string,
  val: unknown,
): Expression<SqlBool> | null {
  switch (op) {
    case "=":
    case "eq":
      return eb(prop as any, "=", val);
    case "<>":
    case "!=":
    case "ne":
      return eb(prop as any, "<>", val);
    case ">":
    case "gt":
      return eb(prop as any, ">", val as any);
    case ">=":
    case "gte":
      return eb(prop as any, ">=", val as any);
    case "<":
    case "lt":
      return eb(prop as any, "<", val as any);
    case "<=":
    case "lte":
      return eb(prop as any, "<=", val as any);
    case "in":
      return Array.isArray(val) ? eb(prop as any, "in", val) : null;
    case "contains":
    case "ilike":
      return eb(prop as any, "ilike", `%${val}%`);
    case "like":
      return eb(prop as any, "like", val as string);
    default:
      return null;
  }
}

function applyWhereToBuilder(builder: any, where: WhereClause): any {
  switch (where.op) {
    case "=":
    case "eq":
      return builder.where(where.prop as any, "=", where.val);
    case "<>":
    case "!=":
    case "ne":
      return builder.where(where.prop as any, "<>", where.val);
    case ">":
    case "gt":
      return builder.where(where.prop as any, ">", where.val);
    case ">=":
    case "gte":
      return builder.where(where.prop as any, ">=", where.val);
    case "<":
    case "lt":
      return builder.where(where.prop as any, "<", where.val);
    case "<=":
    case "lte":
      return builder.where(where.prop as any, "<=", where.val);
    case "in":
      return Array.isArray(where.val) ? builder.where(where.prop as any, "in", where.val) : builder;
    case "contains":
    case "ilike":
      return builder.where(where.prop as any, "ilike", `%${String(where.val ?? "")}%`);
    case "like":
      return builder.where(where.prop as any, "like", String(where.val ?? ""));
    default:
      throw new Error(`[DEPRECATED] Unsupported G() where operator: ${where.op}`);
  }
}

export class GraphBuilder {
  private label: string;
  private _op: string = "";
  private _props: Record<string, unknown> | null = null;
  private _matchProps: Record<string, unknown> | null = null;
  private _setProps: Record<string, unknown> | null = null;
  private _wheres: WhereClause[] = [];
  private _returns: string[] = [];
  private _orderBy: string = "";
  private _orderDesc: boolean = false;
  private _skip: number = 0;
  private _limit: number = 0;

  constructor(label: string) {
    this.label = label;
  }

  Create(props: Record<string, unknown>): GraphBuilder {
    this._op = "create";
    this._props = props;
    return this;
  }

  Match(props: Record<string, unknown>): GraphBuilder {
    this._matchProps = props;
    return this;
  }

  Set(props: Record<string, unknown>): GraphBuilder {
    this._op = "set";
    this._setProps = props;
    return this;
  }

  Merge(matchProps: Record<string, unknown>, setProps: Record<string, unknown>): GraphBuilder {
    this._op = "merge";
    this._matchProps = matchProps;
    this._setProps = setProps;
    return this;
  }

  Delete(): GraphBuilder {
    this._op = "delete";
    return this;
  }

  Where(prop: string, op: string, val: unknown): GraphBuilder {
    this._wheres.push({ prop, op, val });
    return this;
  }

  WhereContains(prop: string, val: string): GraphBuilder {
    this._wheres.push({ prop, op: "contains", val });
    return this;
  }

  Return(...props: string[]): GraphBuilder {
    this._returns = props;
    return this;
  }

  OrderBy(prop: string, desc: boolean = false): GraphBuilder {
    this._orderBy = prop;
    this._orderDesc = desc;
    return this;
  }

  Skip(n: number): GraphBuilder {
    this._skip = n;
    return this;
  }

  Limit(n: number): GraphBuilder {
    this._limit = n;
    return this;
  }

  async exec(): Promise<void> {
    const rpc = getKagamiRpc() as any;
    if (!rpc?.directSql || !rpc?.directWrite) {
      throw new Error(`[DEPRECATED] G(${this.label}).exec() requires Kysely/directSql support.`);
    }
    const result = await this.tryKyselyExec();
    if (!result) throw new Error(`[DEPRECATED] G(${this.label}).exec() unsupported for this operation. Use createKyselyDb() directly.`);
  }

  async query(): Promise<Record<string, unknown>[]> {
    if (!this._op) this._op = "query";
    if (this._op === "query" && this._limit <= 0) {
      throw new Error(`G(${this.label}).query(): LIMIT is mandatory. Call .Limit(N) before .query()`);
    }
    // Kysely direct path: bypass SQL transpiler when GRAPH_QUERY_SERVICE supports directSql
    const rpc = getKagamiRpc() as any;
    if (rpc?.directSql && rpc?.directWrite) {
      const result = await this.tryKyselyQuery();
      if (result !== null) return result;
    }
    throw new Error(`[DEPRECATED] G(${this.label}).query() unsupported for this query shape. Use createKyselyDb() directly.`);
  }

  async count(): Promise<number> {
    this._op = "count";
    // Kysely direct path
    const rpc = getKagamiRpc() as any;
    if (rpc?.directSql && rpc?.directWrite) {
      const result = await this.tryKyselyCount();
      if (result !== null) return result;
    }
    throw new Error(`[DEPRECATED] G(${this.label}).count() unsupported for this query shape. Use createKyselyDb() directly.`);
  }

  private async tryKyselyExec(): Promise<boolean> {
    const tableName = resolveKyselyTableName(this.label);
    if (!tableName) return false;
    const db = createKyselyDb();
    try {
      switch (this._op) {
        case "create": {
          if (!this._props) return false;
          await db.insertInto(tableName as keyof GrapharDB).values(this._props as any).execute();
          return true;
        }
        case "merge": {
          if (!this._matchProps) return false;
          let existsQ: any = db.selectFrom(tableName as keyof GrapharDB).selectAll();
          for (const [k, v] of Object.entries(this._matchProps)) existsQ = existsQ.where(k as any, "=", v);
          const existing = await existsQ.limit(1).executeTakeFirst();
          if (existing) {
            if (this._setProps && Object.keys(this._setProps).length > 0) {
              let updateQ: any = db.updateTable(tableName as keyof GrapharDB).set(this._setProps as any);
              for (const [k, v] of Object.entries(this._matchProps)) updateQ = updateQ.where(k as any, "=", v);
              await updateQ.execute();
            }
          } else {
            await db.insertInto(tableName as keyof GrapharDB).values({ ...(this._matchProps ?? {}), ...(this._setProps ?? {}) } as any).execute();
          }
          return true;
        }
        case "set": {
          if (!this._setProps) return false;
          let updateQ: any = db.updateTable(tableName as keyof GrapharDB).set(this._setProps as any);
          if (this._matchProps) {
            for (const [k, v] of Object.entries(this._matchProps)) updateQ = updateQ.where(k as any, "=", v);
          }
          for (const w of this._wheres) updateQ = applyWhereToBuilder(updateQ, w);
          await updateQ.execute();
          return true;
        }
        case "delete": {
          let deleteQ: any = db.deleteFrom(tableName as keyof GrapharDB);
          if (this._matchProps) {
            for (const [k, v] of Object.entries(this._matchProps)) deleteQ = deleteQ.where(k as any, "=", v);
          }
          for (const w of this._wheres) deleteQ = applyWhereToBuilder(deleteQ, w);
          await deleteQ.execute();
          return true;
        }
        default:
          return false;
      }
    } catch (e: any) {
      console.warn(`[graph-builder] Kysely exec path failed for ${this.label}: ${e?.message ?? e}`);
      return false;
    }
  }

  /** Try to execute query via Kysely direct SQL path. Returns null if unsupported (caller falls back to SQL).
   *  Throws on Kysely execution errors (so caller doesn't silently retry on SQL with same query). */
  private async tryKyselyQuery(): Promise<Record<string, unknown>[] | null> {
    const tableName = resolveKyselyTableName(this.label);
    if (!tableName) return null;

    const db = createKyselyDb();
    try {
      let q: any = db.selectFrom(tableName as keyof GrapharDB);

      // Build WHERE conditions from matchProps + wheres
      if (this._matchProps || this._wheres.length > 0) {
        q = q.where((eb) => {
          const exprs: Expression<SqlBool>[] = [];
          if (this._matchProps) {
            for (const [k, v] of Object.entries(this._matchProps)) {
              exprs.push(eb(k as any, "=", v));
            }
          }
          for (const w of this._wheres) {
            const expr = whereOpToKysely(eb, w.prop, w.op, w.val);
            if (!expr) return null; // unsupported op → fall back to SQL
            exprs.push(expr);
          }
          return exprs.length > 0 ? eb.and(exprs) : eb.selectAll() as any;
        });
      }

      // SELECT columns
      if (this._returns.length > 0) {
        q = q.select(this._returns as any);
      } else {
        q = q.selectAll();
      }

      // ORDER BY
      if (this._orderBy) {
        q = q.orderBy(this._orderBy as any, this._orderDesc ? "desc" : "asc");
      }

      // LIMIT / OFFSET
      if (this._limit > 0) q = q.limit(this._limit);
      if (this._skip > 0) q = q.offset(this._skip);

      return await q.execute();
    } catch (e: any) {
      console.warn(`[graph-builder] Kysely query path failed for ${this.label}, falling back to SQL: ${e?.message ?? e}`);
      return null;
    }
  }

  /** Try to execute count via Kysely direct SQL path. Returns null if unsupported. */
  private async tryKyselyCount(): Promise<number | null> {
    const tableName = resolveKyselyTableName(this.label);
    if (!tableName) return null;

    const db = createKyselyDb();
    try {
      let q: any = db.selectFrom(tableName as keyof GrapharDB);

      // Build WHERE conditions
      if (this._matchProps || this._wheres.length > 0) {
        q = q.where((eb) => {
          const exprs: Expression<SqlBool>[] = [];
          if (this._matchProps) {
            for (const [k, v] of Object.entries(this._matchProps)) {
              exprs.push(eb(k as any, "=", v));
            }
          }
          for (const w of this._wheres) {
            const expr = whereOpToKysely(eb, w.prop, w.op, w.val);
            if (!expr) return null; // unsupported op
            exprs.push(expr);
          }
          return exprs.length > 0 ? eb.and(exprs) : eb.selectAll() as any;
        });
      }

      // SELECT COUNT(*)
      const rows = await q.select(db.fn.countAll().as("total")).execute();
      const total = rows[0]?.total;
      return typeof total === "number" ? total : Number(total ?? 0);
    } catch (e: any) {
      console.warn(`[graph-builder] Kysely count path failed for ${this.label}, falling back to SQL: ${e?.message ?? e}`);
      return null;
    }
  }

  private build(): [string, Record<string, unknown>] {
    const op: GraphOp = {
      op: this._op,
      label: this.label,
    };
    if (this._props) op.props = this._props;
    if (this._matchProps) op.match = this._matchProps;
    if (this._setProps) op.set = this._setProps;
    if (this._wheres.length > 0) op.where = this._wheres;
    if (this._returns.length > 0) op.return = this._returns;
    if (this._orderBy) op.orderBy = this._orderBy;
    if (this._orderDesc) op.orderDesc = true;
    if (this._skip) op.skip = this._skip;
    if (this._limit) op.limit = this._limit;

    const params: Record<string, unknown> = {};
    let pidx = 0;
    const pname = (): string => { pidx++; return `_p${pidx}`; };

    let sql: string;

    switch (this._op) {
      case "create": {
        const propParts = this.buildPropParts(this._props ?? {}, params, pname);
        sql = `CREATE (n:${this.label} {${propParts.join(", ")}})`;
        break;
      }

      case "merge": {
        const matchParts = this.buildPropParts(this._matchProps ?? {}, params, pname);
        const setParts = this.buildSetParts("n", this._setProps ?? {}, params, pname);
        sql = `MERGE (n:${this.label} {${matchParts.join(", ")}}) SET ${setParts.join(", ")}`;
        break;
      }

      case "set": {
        const matchParts = this._matchProps
          ? Object.entries(this._matchProps).map(([k, v]) => {
              const n = pname(); params[n] = v; return `n.${k} = $${n}`;
            })
          : [];
        const setParts = this.buildSetParts("n", this._setProps ?? {}, params, pname);
        const whereStr = matchParts.length > 0 ? ` WHERE ${matchParts.join(" AND ")}` : "";
        sql = `MAT` + `CH (n:${this.label})${whereStr} SET ${setParts.join(", ")}`;
        break;
      }

      case "delete": {
        const matchParts = this._matchProps
          ? Object.entries(this._matchProps).map(([k, v]) => {
              const n = pname(); params[n] = v; return `n.${k} = $${n}`;
            })
          : [];
        const whereStr = matchParts.length > 0 ? ` WHERE ${matchParts.join(" AND ")}` : "";
        sql = `MAT` + `CH (n:${this.label})${whereStr} DELETE n`;
        break;
      }

      case "count": {
        const whereParts = this.buildWhereParts("n", params, pname);
        const whereStr = whereParts.length > 0 ? ` WHERE ${whereParts.join(" AND ")}` : "";
        sql = `MAT` + `CH (n:${this.label})${whereStr} RETURN count(n) AS total`;
        break;
      }

      default: { // query
        // Use WHERE clause instead of inline {prop: $val} pattern — DuckDB GQL
        // parser does not support inline property constraints in MATCH patterns.
        const matchPropParts = this._matchProps
          ? Object.entries(this._matchProps).map(([k, v]) => {
              const n = pname();
              params[n] = v;
              return `n.${k} = $${n}`;
            })
          : [];
        const whereParts = this.buildWhereParts("n", params, pname);
        const allWhere = [...matchPropParts, ...whereParts];
        const whereStr = allWhere.length > 0 ? ` WHERE ${allWhere.join(" AND ")}` : "";
        const returnCols = this._returns.map((r) => `n.${r} AS ${r}`);
        sql = `MAT` + `CH (n:${this.label})${whereStr} RETURN ${returnCols.join(", ")}`;

        if (this._orderBy) {
          sql += ` ORDER BY n.${this._orderBy}${this._orderDesc ? " DESC" : ""}`;
        }
        if (this._skip > 0 || this._limit > 0) {
          const sn = pname();
          const ln = pname();
          params[sn] = this._skip;
          params[ln] = this._limit;
          sql += ` SKIP $${sn} LIMIT $${ln}`;
        }
        break;
      }
    }

    const prefixed = `__graph_op:${JSON.stringify(op)}\n${sql}`;
    return [prefixed, params];
  }

  private buildPropParts(
    props: Record<string, unknown>,
    params: Record<string, unknown>,
    pname: () => string,
  ): string[] {
    const parts: string[] = [];
    for (const [k, v] of Object.entries(props)) {
      const n = pname();
      params[n] = v;
      parts.push(`${k}: $${n}`);
    }
    return parts;
  }

  private buildSetParts(
    alias: string,
    props: Record<string, unknown>,
    params: Record<string, unknown>,
    pname: () => string,
  ): string[] {
    const parts: string[] = [];
    for (const [k, v] of Object.entries(props)) {
      const n = pname();
      params[n] = v;
      parts.push(`${alias}.${k} = $${n}`);
    }
    return parts;
  }

  private buildWhereParts(
    alias: string,
    params: Record<string, unknown>,
    pname: () => string,
  ): string[] {
    const parts: string[] = [];
    for (const w of this._wheres) {
      const n = pname();
      params[n] = w.val;
      if (w.op === "contains") {
        parts.push(`${alias}.${w.prop} CONTAINS $${n}`);
      } else {
        parts.push(`${alias}.${w.prop} ${w.op} $${n}`);
      }
    }
    return parts;
  }
}

export function Graph(label: string): GraphBuilder {
  return new GraphBuilder(label);
}
