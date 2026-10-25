// nsid.ts — NSID utilities (Single Source of Truth).

/** AT Protocol collection NSID → SQL label (PascalCase).
 *
 * Handles both kebab-case and snakeCase segments.
 * e.g. "app.bsky.feed.post" → "Post"
 *      "com.etzhayyim.actor.app" → "App"
 *      "com.etzhayyim.apps.handotai.supply-chain" → "SupplyChain"
 */
export function collectionToLabel(collection: string): string {
  if (!collection) return "";
  const parts = collection.split(".");
  const last = parts[parts.length - 1];
  if (!last) return "";
  return last
    .split(/[-_]/)
    .map((seg) => seg.charAt(0).toUpperCase() + seg.slice(1))
    .join("");
}

/** Expand short kind to full NSID.
 *
 * e.g. expandCollection("machine", "pachinko") → "com.etzhayyim.apps.pachinko.machine"
 *      expandCollection("app.bsky.feed.post") → "app.bsky.feed.post" (passthrough)
 */
export function expandCollection(kind: string, appName?: string): string {
  if (!kind || kind.includes(".")) return kind;
  return appName ? `com.etzhayyim.apps.${appName}.${kind}` : kind;
}

/** WIT package + type → AT Protocol collection NSID.
 *
 * e.g. witToCollection("etzhayyim:handotai", "article") → "com.etzhayyim.apps.handotai.article"
 *      witToCollection("kotodama:wproto", "record") → "com.etzhayyim.platform.wproto.record"
 */
export function witToCollection(witPkg: string, witType: string): string {
  const ns = witPkg.startsWith("etzhayyim:") ? "com.etzhayyim.apps" : "com.etzhayyim.platform";
  const app = witPkg.split(":")[1]?.split("/")[0] ?? witPkg;
  return `${ns}.${app}.${witType}`;
}

/** NSID → PascalCase method name (convention-based, 95%+ coverage).
 *
 * Only 13 overrides for irregular mappings across 370+ NSIDs.
 */
export function nsidToMethod(nsid: string): string {
  const OVERRIDES: Record<string, string> = {
    "com.atproto.repo.importRepo": "ImportRepoCar",
    "com.atproto.server.deleteAccount": "ServerDeleteAccount",
    "com.atproto.admin.searchRepos": "AdminSearchAccounts",
    "app.bsky.notification.getUnreadCount": "GetNotificationCount",
    "app.bsky.notification.updateSeen": "UpdateNotificationSeen",
    "app.bsky.notification.putPreferences": "PutNotificationPreferences",
    "chat.bsky.convo.sendMessage": "SendChatMessage",
    "chat.bsky.actor.getMetadata": "GetChatActorMetadata",
    "chat.bsky.actor.deleteAccount": "ChatActorDeleteAccount",
    "chat.bsky.actor.exportAccountData": "ChatActorExportAccountData",
    "chat.bsky.actor.declaration": "ChatActorDeclaration",
    "chat.bsky.actor.updateAccess": "UpdateChatActorAccess",
    "chat.bsky.moderation.getMessageContext": "GetChatMessageContext",
  };
  if (OVERRIDES[nsid]) return OVERRIDES[nsid];

  const segments = nsid.split(".");
  const last = segments[segments.length - 1];
  const base = last.charAt(0).toUpperCase() + last.slice(1);

  const ns = segments.slice(0, -1).join(".");
  if (ns.startsWith("com.atproto.admin")) return `Admin${base}`;
  if (ns.startsWith("com.atproto.sync")) return `Sync${base}`;
  if (ns.startsWith("com.atproto.temp")) return `Temp${base}`;
  if (ns.startsWith("app.bsky.unspecced")) return `Unspecced${base}`;
  if (ns.startsWith("tools.ozone.moderation")) return `Ozone${base}`;
  if (ns.startsWith("tools.ozone.communication")) return `Ozone${base}`;
  if (ns.startsWith("tools.ozone.server")) return `Ozone${base}`;
  if (ns.startsWith("tools.ozone.team")) return `OzoneTeam${base}`;
  if (ns.startsWith("tools.ozone.setting")) return `OzoneSetting${base}`;
  if (ns.startsWith("tools.ozone.set")) return `OzoneSet${base}`;
  if (ns.startsWith("tools.ozone.signature")) return `OzoneSignature${base}`;
  if (ns.startsWith("tools.ozone.verification")) return `Ozone${base}`;
  if (ns.startsWith("tools.ozone.hosting")) return `Ozone${base}`;

  return base;
}

/** Build app namespace NSID prefix.
 *
 * e.g. appNamespace("site") -> "com.etzhayyim.apps.site"
 */
export function appNamespace(domain: string): string {
  return `com.etzhayyim.apps.${domain}`;
}

/** Default collection NSID for an app domain + PascalCase label.
 *
 * e.g. defaultAppCollection("site", "Article") -> "com.etzhayyim.apps.site.article"
 */
export function defaultAppCollection(domain: string, label: string): string {
  const ns = appNamespace(domain);
  return `${ns}.${label.charAt(0).toLowerCase()}${label.slice(1)}`;
}

/** W protocol lexicon suffix -> collection NSID.
 *
 * e.g. wLexiconCollection("message") -> "com.etzhayyim.w.message"
 */
export function wLexiconCollection(suffix: string): string {
  return `com.etzhayyim.w.${suffix}`;
}

/** Resolve flat dispatcher method into canonical app NSID. */
export function resolveFlatDispatchMethod(
  flatMethod: string,
  registeredNsids: Iterable<string>,
): string | null {
  if (!flatMethod || flatMethod.includes(".")) return null;

  for (const key of registeredNsids) {
    const parts = key.split(".");
    if (parts.length < 5 || parts[0] !== "com" || parts[1] !== "etzhayyim" || parts[2] !== "apps") {
      continue;
    }
    const appName = parts[3];
    const suffix = `_${appName}`;
    if (!flatMethod.endsWith(suffix)) continue;
    const snake = flatMethod.slice(0, -suffix.length);
    const camel = snake.replace(/_([a-z])/g, (_m, c: string) => c.toUpperCase());
    return `com.etzhayyim.apps.${appName}.${camel}`;
  }
  return null;
}
