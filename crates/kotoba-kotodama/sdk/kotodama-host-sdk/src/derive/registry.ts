/**
 * Derive rules registry — mirrors kotodama.jsonld `derive.rules[]` for each app.
 *
 * MVP: hardcoded from each app's kotodama.jsonld. A future migration will move
 * this to a graph cache (`vertex_kotodama_config`) populated at `etzhayyim deploy`
 * time, so the PDS Worker reloads rules without a redeploy.
 *
 * Keyed by AT collection NSID — a commit on that collection scans all rules
 * whose `on.collection` matches.
 */

export interface DeriveRule {
  id: string;
  app: string;
  on: { collection: string; action: "create" | "update" | "delete"; where?: Record<string, unknown> };
  emit: {
    type: "app.bsky.feed.post";
    did: string;
    text: string;
    facets?: unknown[];
    embed?: unknown;
    reply?: unknown;
    _meta?: Record<string, unknown>;
  };
}

export const DERIVE_RULES: DeriveRule[] = [
  // mangaka — 60-apps/etzhayyim-project-mangaka/.../kotodama.jsonld
  {
    id: "chapter-published-social",
    app: "mangaka",
    on: {
      collection: "com.etzhayyim.apps.mangaka.chapter",
      action: "create",
      where: { "record.status": "published" },
    },
    emit: {
      type: "app.bsky.feed.post",
      did: "{{resolve(record.workRef).workDid}}",
      text: "📖 新章公開  {{record.volumeId}} ch.{{record.chapterNum}} — {{record.titleJP}}\n{{charactersAppearingMentions record.charactersAppearing}}{{arcIdsTags record.arcIds}}#{{tagFromVolume record.volumeId}}\nRead → {{record.readerUri}}",
      facets: [
        {
          _from: "record.charactersAppearing",
          _each: {
            index: { _matchText: "@{{item.displayName}}" },
            features: [
              {
                $type: "app.bsky.richtext.facet#mention",
                did: "did:web:mangaka.etzhayyim.com:character:{{item.slug}}",
              },
            ],
          },
        },
        {
          _from: "record.arcIds",
          _each: {
            index: { _matchText: "#{{item}}" },
            features: [{ $type: "app.bsky.richtext.facet#tag", tag: "{{item}}" }],
          },
        },
        {
          index: { _matchText: "#{{tagFromVolume record.volumeId}}" },
          features: [
            { $type: "app.bsky.richtext.facet#tag", tag: "{{tagFromVolume record.volumeId}}" },
          ],
        },
        {
          index: { _matchText: "{{record.readerUri}}" },
          features: [{ $type: "app.bsky.richtext.facet#link", uri: "{{record.readerUri}}" }],
        },
      ],
      embed: {
        $type: "app.bsky.embed.images",
        images: [
          {
            image: { $type: "blob", ref: { $link: "{{record.coverCid}}" }, mimeType: "image/png" },
            alt: "{{record.coverAlt}}",
          },
        ],
      },
      _meta: {
        sideEffect: "linkBackPostUri",
        linkBackField: "chapterPostUri",
        linkBackTarget: "{{self.uri}}",
      },
    },
  },
  {
    id: "page-published-social",
    app: "mangaka",
    on: { collection: "com.etzhayyim.apps.mangaka.page", action: "create" },
    emit: {
      type: "app.bsky.feed.post",
      did: "{{resolve(record.chapterRef).workDid}}",
      text: "p.{{record.pageNum}} {{charactersAppearingMentions record.charactersAppearing}}",
      reply: {
        root: "{{derived(record.chapterRef).strongRef}}",
        parent: "{{derived(record.chapterRef).strongRef}}",
      },
      facets: [
        {
          _from: "record.charactersAppearing",
          _each: {
            index: { _matchText: "@{{item.displayName}}" },
            features: [
              {
                $type: "app.bsky.richtext.facet#mention",
                did: "did:web:mangaka.etzhayyim.com:character:{{item.slug}}",
              },
            ],
          },
        },
      ],
      embed: {
        $type: "app.bsky.embed.images",
        images: [
          {
            image: { $type: "blob", ref: { $link: "{{record.compositedImageCid}}" }, mimeType: "image/jpeg" },
            alt: "{{record.altText}}",
            aspectRatio: { width: "{{record.width}}", height: "{{record.height}}" },
          },
        ],
      },
    },
  },
];

/** Return rules that match a committed collection. */
export function rulesForCollection(collection: string): DeriveRule[] {
  return DERIVE_RULES.filter((r) => r.on.collection === collection);
}
