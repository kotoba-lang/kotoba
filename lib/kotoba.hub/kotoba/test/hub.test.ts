import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerRepository,
  getRepository,
  listRepositories,
  createCommitStatus,
  listCommitStatuses,
  openPullRequest,
  listPullRequests,
  getPullRequest,
  recordCheckRun,
  listCheckRuns,
  registerWebhook,
  listWebhooks,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:hub.etzhayyim.com";

describe("hub kotoba (GitHub-compatible, kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("repository (PLAINTEXT public catalog)", () => {
    it("registers, dedups, validates, gets, lists/filters", async () => {
      expect((await registerRepository(e, { owner: "etzhayyim", name: "root" })).status).toBe("registered");
      expect((await registerRepository(e, { owner: "etzhayyim", name: "root" })).status).toBe("alreadyExists");
      expect((await registerRepository(e, { owner: "", name: "x" })).status).toBe("rejected");
      expect((await registerRepository(e, { owner: "o", name: "n", visibility: "secret" })).status).toBe("rejected");
      await registerRepository(e, { owner: "etzhayyim", name: "sdk", visibility: "private", description: "sdk" });
      const got = await getRepository(e, { owner: "etzhayyim", name: "root" });
      expect(got.repository?.slug).toBe("etzhayyim/root");
      expect(got.repository?.defaultBranch).toBe("main");
      expect((await getRepository(e, { owner: "etzhayyim", name: "ghost" })).error).toBe("notFound");
      expect((await listRepositories(e)).total).toBe(2);
      expect((await listRepositories(e, { visibility: "private" })).total).toBe(1);
      expect((await listRepositories(e, { owner: "etzhayyim" })).total).toBe(2);
    });
  });

  describe("commitStatus (PLAINTEXT public CI fact, FK -> repository)", () => {
    it("rejects status on unknown repo, creates on known, dedups, lists/filters", async () => {
      expect((await createCommitStatus(e, { owner: "etzhayyim", name: "root", sha: "abc", context: "ci/build", state: "pending" })).status).toBe("rejected");
      await registerRepository(e, { owner: "etzhayyim", name: "root" });
      expect((await createCommitStatus(e, { owner: "etzhayyim", name: "root", sha: "abc", context: "ci/build", state: "success", targetUrl: "https://ci/1" })).status).toBe("created");
      expect((await createCommitStatus(e, { owner: "etzhayyim", name: "root", sha: "abc", context: "ci/build", state: "success" })).status).toBe("alreadyExists");
      await createCommitStatus(e, { owner: "etzhayyim", name: "root", sha: "def", context: "ci/test", state: "failure" });
      expect((await listCommitStatuses(e)).total).toBe(2);
      expect((await listCommitStatuses(e, { owner: "etzhayyim", name: "root", sha: "abc" })).total).toBe(1);
    });
  });

  describe("pullRequest (E2E-ENCRYPTED confidential review content)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await openPullRequest(e, {
        prId: "pr1", owner: "etzhayyim", name: "root", number: 42, title: "feat: split",
        body: "confidential change", headSha: "deadbeef", baseRef: "main", authorDid: "did:web:dev.example",
      });
      expect(ok.status).toBe("opened");
      expect(ok.keyId).toBeTruthy();
      expect((await openPullRequest(e, { prId: "prX", owner: "o", name: "n", number: -1, title: "t", headSha: "s", baseRef: "main", authorDid: "d" })).status).toBe("rejected");
      const got = await getPullRequest(e, { prId: "pr1" });
      expect(got.pullRequest?.title).toBe("feat: split");
      expect(got.pullRequest?.number).toBe(42);
      expect(got.pullRequest?.authorDid).toBe("did:web:dev.example");
      expect((await getPullRequest(e, { prId: "ghost" })).error).toBe("notFound");
      await openPullRequest(e, { prId: "pr2", owner: "etzhayyim", name: "sdk", number: 7, title: "fix", headSha: "cafe", baseRef: "main", authorDid: "did:web:d2", state: "merged" });
      expect((await listPullRequests(e)).total).toBe(2);
      expect((await listPullRequests(e, { state: "open" })).total).toBe(1);
      expect((await listPullRequests(e, { slug: "etzhayyim/sdk" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the PR", async () => {
      await openPullRequest(e, { prId: "pr1", owner: "etzhayyim", name: "root", number: 1, title: "t", headSha: "s", baseRef: "main", authorDid: "did:web:dev" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listPullRequests(outsider)).total).toBe(0);
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await openPullRequest(e, { prId: "pr1", owner: "etzhayyim", name: "root", number: 1, title: "t", headSha: "s", baseRef: "main", authorDid: "did:web:dev", recipients: [partner] });
      expect(r.status).toBe("opened");
      expect((await listPullRequests(e)).total).toBe(1);
    });
  });

  describe("checkRun (E2E-ENCRYPTED CUI scanner output)", () => {
    it("seals + round-trips + filters by slug/sha", async () => {
      const r = await recordCheckRun(e, { checkRunId: "ck1", owner: "etzhayyim", name: "root", sha: "abc", checkName: "secret-scan", status: "completed", conclusion: "success", summary: "no findings" });
      expect(r.status).toBe("recorded");
      expect(r.keyId).toBeTruthy();
      expect((await recordCheckRun(e, { checkRunId: "", owner: "o", name: "n", sha: "s", checkName: "c", status: "queued" })).status).toBe("rejected");
      await recordCheckRun(e, { checkRunId: "ck2", owner: "etzhayyim", name: "root", sha: "def", checkName: "lint", status: "in_progress" });
      expect((await listCheckRuns(e)).total).toBe(2);
      expect((await listCheckRuns(e, { sha: "abc" })).total).toBe(1);
      expect((await listCheckRuns(e, { slug: "etzhayyim/root" })).total).toBe(2);
    });

    it("enforces read-cap on check runs", async () => {
      await recordCheckRun(e, { checkRunId: "ck1", owner: "etzhayyim", name: "root", sha: "abc", checkName: "scan", status: "completed", conclusion: "failure" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listCheckRuns(outsider)).total).toBe(0);
    });
  });

  describe("webhook (E2E-ENCRYPTED confidential delivery config)", () => {
    it("seals + round-trips + validates events", async () => {
      const r = await registerWebhook(e, { webhookId: "wh1", owner: "etzhayyim", name: "root", targetUrl: "https://relay.example/hook", events: ["push", "pull_request"], orgDid: "did:web:org" });
      expect(r.status).toBe("registered");
      expect(r.keyId).toBeTruthy();
      expect((await registerWebhook(e, { webhookId: "whX", owner: "o", name: "n", targetUrl: "https://x", events: [] })).status).toBe("rejected");
      await registerWebhook(e, { webhookId: "wh2", owner: "etzhayyim", name: "sdk", targetUrl: "https://relay/2", events: ["push"] });
      expect((await listWebhooks(e)).total).toBe(2);
      expect((await listWebhooks(e, { slug: "etzhayyim/root" })).total).toBe(1);
    });

    it("enforces read-cap on webhooks", async () => {
      await registerWebhook(e, { webhookId: "wh1", owner: "etzhayyim", name: "root", targetUrl: "https://x", events: ["push"] });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listWebhooks(outsider)).total).toBe(0);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext repos/statuses + E2E PRs/checks/webhooks", async () => {
      await registerRepository(e, { owner: "etzhayyim", name: "root", visibility: "public" });
      await registerRepository(e, { owner: "etzhayyim", name: "sdk", visibility: "private" });
      await createCommitStatus(e, { owner: "etzhayyim", name: "root", sha: "abc", context: "ci", state: "success" });
      await openPullRequest(e, { prId: "pr1", owner: "etzhayyim", name: "root", number: 1, title: "t", headSha: "s", baseRef: "main", authorDid: "did:web:d" });
      await recordCheckRun(e, { checkRunId: "ck1", owner: "etzhayyim", name: "root", sha: "abc", checkName: "scan", status: "completed", conclusion: "success" });
      await registerWebhook(e, { webhookId: "wh1", owner: "etzhayyim", name: "root", targetUrl: "https://x", events: ["push"] });
      const cov = await coverage(e);
      expect(cov.repositoryCount).toBe(2);
      expect(cov.commitStatusCount).toBe(1);
      expect(cov.pullRequestCount).toBe(1);
      expect(cov.checkRunCount).toBe(1);
      expect(cov.webhookCount).toBe(1);
      expect(cov.repositoriesByVisibility?.public).toBe(1);
      expect(cov.repositoriesByVisibility?.private).toBe(1);
    });
  });
});
