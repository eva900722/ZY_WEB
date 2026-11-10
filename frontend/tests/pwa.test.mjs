import test from "node:test";
import assert from "node:assert/strict";
import { privateRoutes, precachePatterns } from "../src/pwaPolicy.ts";
for (const path of [
  "/api/auth/session/",
  "/api/tickets/",
  "/attachments/1/",
  "/reports/pdf/",
  "/accounts/token/test-token/",
  "/legacy/",
]) {
  test("Private navigation never gets cached app fallback: " + path, () =>
    assert.ok(privateRoutes.some((rule) => rule.test(path))),
  );
}
test("Ordinary application routes may open the offline shell", () =>
  assert.ok(!privateRoutes.some((rule) => rule.test("/tickets/new/"))));
test("Precache only targets static build artifacts", () =>
  assert.equal(precachePatterns.length, 1));
