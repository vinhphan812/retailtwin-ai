import { createHash } from "node:crypto";
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  LICENSE_ASSET_NAMES,
  copyLicenseAssets,
  createLicenseTextMiddleware,
  licenseAssetPaths,
  sha256File,
} from "./copy-license-assets";

/** Minimal stand-in for the parts of `ServerResponse` the middleware uses. */
class FakeResponse {
  statusCode = 0;
  headers: Record<string, string> = {};
  body: Buffer | undefined;
  ended = false;

  setHeader(name: string, value: string): void {
    this.headers[name.toLowerCase()] = value;
  }

  end(payload?: Buffer): void {
    if (payload) this.body = payload;
    this.ended = true;
  }
}

function makeRequest(url: string, method = "GET") {
  return { url, method } as never;
}

describe("license asset copy", () => {
  let repoRoot: string;
  let outDir: string;

  beforeEach(() => {
    repoRoot = mkdtempSync(join(tmpdir(), "license-src-"));
    outDir = mkdtempSync(join(tmpdir(), "license-out-"));
    for (const name of LICENSE_ASSET_NAMES) {
      writeFileSync(join(repoRoot, name), `content of ${name}\n`, "utf8");
    }
  });

  afterEach(() => {
    rmSync(repoRoot, { recursive: true, force: true });
    rmSync(outDir, { recursive: true, force: true });
  });

  it("copies every canonical asset into the output directory", () => {
    const results = copyLicenseAssets(repoRoot, outDir);

    expect(results.map((result) => result.name)).toEqual([
      "LICENSE",
      "THIRD_PARTY_NOTICES.md",
    ]);
    for (const name of LICENSE_ASSET_NAMES) {
      expect(readFileSync(join(outDir, name), "utf8")).toBe(
        `content of ${name}\n`,
      );
    }
  });

  it("produces byte-identical copies whose digest matches the source", () => {
    const results = copyLicenseAssets(repoRoot, outDir);

    for (const result of results) {
      const expected = createHash("sha256")
        .update(readFileSync(result.source))
        .digest("hex");
      expect(result.sha256).toBe(expected);
      expect(result.copiedSha256).toBe(expected);
      expect(sha256File(result.destination)).toBe(expected);
      expect(result.bytes).toBe(readFileSync(result.source).byteLength);
    }
  });

  it("preserves the source file timestamps on the published copy", () => {
    const source = join(repoRoot, "LICENSE");

    copyLicenseAssets(repoRoot, outDir);

    // The copy must carry the canonical licence revision's modification time
    // with nanosecond fidelity, not a build-time reading. The access time is
    // deliberately not asserted: hashing the source reads it, which moves the
    // source's own atime.
    const sourceStat = statSync(source, { bigint: true });
    const copiedStat = statSync(join(outDir, "LICENSE"), { bigint: true });
    expect(copiedStat.mtimeNs).toBe(sourceStat.mtimeNs);
  });

  it("fails closed when a canonical source file is missing", () => {
    rmSync(join(repoRoot, "LICENSE"));

    expect(() => copyLicenseAssets(repoRoot, outDir)).toThrow(
      /Canonical licence file\(s\) missing from the repository root: LICENSE/,
    );
  });

  it("does not write a partial bundle when a source file is missing", () => {
    rmSync(join(repoRoot, "THIRD_PARTY_NOTICES.md"));

    // The copy validates every canonical source before writing anything, so a
    // missing file aborts the build instead of publishing a partial bundle.
    expect(() => copyLicenseAssets(repoRoot, outDir)).toThrow(/THIRD_PARTY/);
    expect(existsSync(join(outDir, "LICENSE"))).toBe(false);
    expect(existsSync(join(outDir, "THIRD_PARTY_NOTICES.md"))).toBe(false);
  });

  it("maps every asset name to a path inside the given directory", () => {
    const paths = licenseAssetPaths("/tmp/example");

    expect(paths.LICENSE).toBe(join("/tmp/example", "LICENSE"));
    expect(paths["THIRD_PARTY_NOTICES.md"]).toBe(
      join("/tmp/example", "THIRD_PARTY_NOTICES.md"),
    );
  });
});

describe("license text middleware", () => {
  let repoRoot: string;

  beforeEach(() => {
    repoRoot = mkdtempSync(join(tmpdir(), "license-src-"));
    for (const name of LICENSE_ASSET_NAMES) {
      writeFileSync(join(repoRoot, name), `content of ${name}\n`, "utf8");
    }
  });

  afterEach(() => {
    rmSync(repoRoot, { recursive: true, force: true });
  });

  it("serves the licence as plain text instead of the SPA shell", () => {
    const middleware = createLicenseTextMiddleware(() =>
      licenseAssetPaths(repoRoot),
    );
    const response = new FakeResponse();
    let nextCalled = false;

    middleware(makeRequest("/LICENSE"), response as never, () => {
      nextCalled = true;
    });

    expect(nextCalled).toBe(false);
    expect(response.statusCode).toBe(200);
    expect(response.headers["content-type"]).toBe("text/plain; charset=utf-8");
    expect(response.body?.toString("utf8")).toBe("content of LICENSE\n");
  });

  it("serves the third-party notices as plain text", () => {
    const middleware = createLicenseTextMiddleware(() =>
      licenseAssetPaths(repoRoot),
    );
    const response = new FakeResponse();

    middleware(
      makeRequest("/THIRD_PARTY_NOTICES.md"),
      response as never,
      () => {},
    );

    expect(response.statusCode).toBe(200);
    expect(response.body?.toString("utf8")).toBe(
      "content of THIRD_PARTY_NOTICES.md\n",
    );
  });

  it("passes unrelated routes through to the next middleware", () => {
    const middleware = createLicenseTextMiddleware(() =>
      licenseAssetPaths(repoRoot),
    );
    const response = new FakeResponse();
    let nextCalled = false;

    middleware(makeRequest("/dashboard"), response as never, () => {
      nextCalled = true;
    });

    expect(nextCalled).toBe(true);
    expect(response.ended).toBe(false);
  });

  it("ignores a query string on the licence request", () => {
    const middleware = createLicenseTextMiddleware(() =>
      licenseAssetPaths(repoRoot),
    );
    const response = new FakeResponse();

    middleware(makeRequest("/LICENSE?v=1"), response as never, () => {});

    expect(response.statusCode).toBe(200);
    expect(response.body?.toString("utf8")).toBe("content of LICENSE\n");
  });

  it("does not answer non-GET methods with the file body", () => {
    const middleware = createLicenseTextMiddleware(() =>
      licenseAssetPaths(repoRoot),
    );
    const response = new FakeResponse();
    let nextCalled = false;

    middleware(makeRequest("/LICENSE", "POST"), response as never, () => {
      nextCalled = true;
    });

    expect(nextCalled).toBe(true);
    expect(response.body).toBeUndefined();
  });
});

