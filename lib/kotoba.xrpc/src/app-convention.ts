import { appNamespace, defaultAppCollection } from "./nsid.js";

export interface AutoCrudConventionInput {
  domain: string;
  label: string;
  collection?: string;
  statuses?: string[];
  searchFields?: string[];
}

export interface AutoCrudCommandNames {
  list: string;
  get: string;
  search: string;
  create: string;
  health: string;
  describe: string;
  stats: string;
  export: string;
  summarize: string;
  ingest: string;
  audit: string;
  validate: string;
  wave: string;
}

export interface AutoCrudConvention {
  ns: string;
  collection: string;
  fields: string[];
  statuses: string[];
  command: AutoCrudCommandNames;
}

export function resolveAutoCrudConvention(input: AutoCrudConventionInput): AutoCrudConvention {
  const ns = appNamespace(input.domain);
  const collection = input.collection ?? defaultAppCollection(input.domain, input.label);
  const fields = input.searchFields ?? ["name", "description"];
  const statuses = input.statuses ?? ["active", "draft", "archived", "pending", "completed"];
  return {
    ns,
    collection,
    fields,
    statuses,
    command: {
      list: `${ns}.list`,
      get: `${ns}.get`,
      search: `${ns}.search`,
      create: `${ns}.create`,
      health: `${ns}.health`,
      describe: `${ns}.describe`,
      stats: `${ns}.stats`,
      export: `${ns}.export`,
      summarize: `${ns}.summarize`,
      ingest: `${ns}.ingest`,
      audit: `${ns}.audit`,
      validate: `${ns}.validate`,
      wave: `${ns}.wave`,
    },
  };
}
