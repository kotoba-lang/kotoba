import { wLexiconCollection } from "./nsid.js";

export interface CommandDslEntry<THandler = unknown> {
  name: string;
  handler: THandler;
  lexiconSuffix: string;
}

export interface QueryDslEntry<THandler = unknown> {
  name: string;
  handler: THandler;
}

export type CommandOption<TEntry extends CommandDslEntry<unknown>> = (entry: TEntry) => void;

export function withWLexicon<TEntry extends CommandDslEntry<unknown>>(suffix: string): CommandOption<TEntry> {
  return (entry) => { entry.lexiconSuffix = suffix; };
}

export function registerCommand<THandler, TEntry extends CommandDslEntry<THandler>>(args: {
  entries: TEntry[];
  methodMap: Map<string, THandler>;
  wRoutes: Map<string, string>;
  entry: TEntry;
  opts?: Array<CommandOption<TEntry>>;
}): TEntry {
  const { entries, methodMap, wRoutes, entry } = args;
  const opts = args.opts ?? [];
  for (const opt of opts) opt(entry);
  entries.push(entry);
  methodMap.set(entry.name, entry.handler);
  if (entry.lexiconSuffix) {
    wRoutes.set(wLexiconCollection(entry.lexiconSuffix), entry.name);
  }
  return entry;
}

export function registerQuery<THandler, TEntry extends QueryDslEntry<THandler>>(args: {
  entries: TEntry[];
  methodMap: Map<string, THandler>;
  entry: TEntry;
}): TEntry {
  const { entries, methodMap, entry } = args;
  entries.push(entry);
  methodMap.set(entry.name, entry.handler);
  return entry;
}
