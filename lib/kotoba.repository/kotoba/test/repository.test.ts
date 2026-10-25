import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  createBlob,
  getBlob,
  createTree,
  getTree,
  createCommit,
  getCommit,
  updateRef,
  listRefs,
  coverage,
} from "../src/index.js";

const B1 = "a".repeat(40);
const B2 = "b".repeat(40);
const T1 = "c".repeat(40);
const C1 = "d".repeat(40);
const C2 = "e".repeat(40);

describe("repository kotoba", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: "did:web:repository.etzhayyim.com" });
  });

  describe("blob (content-addressed)", () => {
    it("creates, dedups, validates oid/size, reads back", async () => {
      expect((await createBlob(e, { oid: B1, content: "hello\n", size: 6 })).status).toBe("created");
      expect((await createBlob(e, { oid: B1, content: "hello\n", size: 6 })).status).toBe("alreadyExists");
      expect((await createBlob(e, { oid: "ZZZ", content: "x", size: 1 })).status).toBe("rejected"); // bad oid
      expect((await createBlob(e, { oid: B2, content: "x", size: -1 })).status).toBe("rejected"); // bad size
      expect((await getBlob(e, { oid: B1 })).blob?.content).toBe("hello\n");
      expect((await getBlob(e, { oid: B2 })).error).toBe("notFound");
    });
  });

  describe("tree (entries reference oids)", () => {
    it("creates with validated entries, reads back", async () => {
      const ok = await createTree(e, {
        oid: T1,
        entries: [
          { name: "README.md", type: "blob", oid: B1, mode: 33188 },
          { name: "src", type: "tree", oid: "f".repeat(40), mode: 16384 },
        ],
      });
      expect(ok.status).toBe("created");
      expect((await getTree(e, { oid: T1 })).tree?.entries.length).toBe(2);
      expect((await createTree(e, { oid: T1, entries: [{ name: "x", type: "blob", oid: B1, mode: 0 }] })).status).toBe("alreadyExists");
      expect((await createTree(e, { oid: "9".repeat(40), entries: [{ name: "x", type: "wat" as any, oid: B1, mode: 0 }] })).status).toBe("rejected"); // bad type
    });
  });

  describe("commit (FK → tree)", () => {
    beforeEach(async () => {
      await createTree(e, { oid: T1, entries: [{ name: "README.md", type: "blob", oid: B1, mode: 33188 }] });
    });
    it("creates FK→tree, rejects missing tree, chains parents", async () => {
      expect((await createCommit(e, { oid: C1, treeOid: "0".repeat(40), message: "x" })).status).toBe("treeNotFound");
      expect((await createCommit(e, { oid: C1, treeOid: T1, message: "init" })).status).toBe("created");
      expect((await createCommit(e, { oid: C2, treeOid: T1, message: "second", parentOids: [C1] })).status).toBe("created");
      const got = await getCommit(e, { oid: C2 });
      expect(got.commit?.parentOids).toContain(C1);
      expect(got.commit?.message).toBe("second");
    });
  });

  describe("ref (FK → commit; mutable pointer)", () => {
    beforeEach(async () => {
      await createTree(e, { oid: T1, entries: [{ name: "f", type: "blob", oid: B1, mode: 33188 }] });
      await createCommit(e, { oid: C1, treeOid: T1, message: "init" });
      await createCommit(e, { oid: C2, treeOid: T1, message: "second", parentOids: [C1] });
    });
    it("creates then fast-forwards a branch ref; lists/filters", async () => {
      expect((await updateRef(e, { refId: "refs/heads/main", targetOid: "1".repeat(40) })).status).toBe("commitNotFound");
      expect((await updateRef(e, { refId: "refs/heads/main", targetOid: C1 })).status).toBe("created");
      const ff = await updateRef(e, { refId: "refs/heads/main", targetOid: C2 });
      expect(ff.status).toBe("updated");
      await updateRef(e, { refId: "refs/tags/v1", targetOid: C1, refType: "tag" });
      expect((await listRefs(e, { refType: "branch" })).total).toBe(1);
      expect((await listRefs(e, { prefix: "refs/tags" })).total).toBe(1);
    });
  });

  describe("coverage", () => {
    it("rolls up object counts + refs by type", async () => {
      await createBlob(e, { oid: B1, content: "x", size: 1 });
      await createTree(e, { oid: T1, entries: [{ name: "f", type: "blob", oid: B1, mode: 33188 }] });
      await createCommit(e, { oid: C1, treeOid: T1, message: "init" });
      await updateRef(e, { refId: "refs/heads/main", targetOid: C1 });
      await updateRef(e, { refId: "refs/tags/v1", targetOid: C1, refType: "tag" });
      const cov = await coverage(e);
      expect(cov.blobCount).toBe(1);
      expect(cov.treeCount).toBe(1);
      expect(cov.commitCount).toBe(1);
      expect(cov.refCount).toBe(2);
      expect(cov.refsByType?.branch).toBe(1);
      expect(cov.refsByType?.tag).toBe(1);
    });
  });
});
