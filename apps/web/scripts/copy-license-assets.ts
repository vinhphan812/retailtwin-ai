import { createHash } from "node:crypto";
import { copyFileSync, existsSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";
// `vitest/config` re-exports Vite's `Plugin` type. `vite.config.ts` builds its
// plugin array with `defineConfig` from the same module, so importing the type
// from here keeps the plugin assignable to that array.
import type { Plugin } from "vitest/config";

/**
 * Canonical licence artefacts that must ship inside the built web bundle.
 *
 * The single source of truth is the repository root. The build copies these
 * files verbatim into the Vite output directory so the deployed bundle carries
 * the licence material without any transformation (no minification, no line
 * ending rewriting, no content rewriting).
 */
export const LICENSE_ASSET_NAMES = ["LICENSE", "THIRD_PARTY_NOTICES.md"] as const;

export type LicenseAssetName = (typeof LICENSE_ASSET_NAMES)[number];

export interface LicenseAssetCopyResult {
  /** File name inside the output directory. */
  name: LicenseAssetName;
  /** Absolute path of the canonical source file in the repository root. */
  source: string;
  /** Absolute path of the copy written into the build output directory. */
  destination: string;
  /** Byte length of the source file. */
  bytes: number;
  /** SHA-256 of the source file, lowercase hex. */
  sha256: string;
  /** SHA-256 of the written copy, lowercase hex. */
  copiedSha256: string;
}

/** Resolves the absolute path of a canonical licence asset inside the repository root. */
export function resolveLicenseSourcePath(
  repoRoot: string,
  name: LicenseAssetName,
): string {
  return join(repoRoot, name);
}

/** Computes the lowercase hex SHA-256 digest of a file. */
export function sha256File(filePath: string): string {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex");
}

/**
 * Maps every canonical licence asset name to its absolute path inside `dir`.
 *
 * The same helper resolves the repository root (source of truth) and the build
 * output directory (published copy).
 */
export function licenseAssetPaths(
  dir: string,
): Record<LicenseAssetName, string> {
  return {
    LICENSE: join(dir, "LICENSE"),
    "THIRD_PARTY_NOTICES.md": join(dir, "THIRD_PARTY_NOTICES.md"),
  };
}

/**
 * Copies the canonical licence assets from the repository root into `outDir`.
 *
 * The copy is byte-for-byte identical to the source: the digest of the source
 * and of the written file are compared and a mismatch aborts the build.
 *
 * The build fails closed when a canonical source file is missing, so a bundle
 * can never be published without its licence material.
 */
export function copyLicenseAssets(
  repoRoot: string,
  outDir: string,
): LicenseAssetCopyResult[] {
  const missing = LICENSE_ASSET_NAMES.filter(
    (name) => !existsSync(resolveLicenseSourcePath(repoRoot, name)),
  );
  if (missing.length > 0) {
    throw new Error(
      `Canonical licence file(s) missing from the repository root: ${missing.join(", ")}. ` +
        `Expected at: ${repoRoot}. Refusing to build a web bundle without its licence material.`,
    );
  }

  return LICENSE_ASSET_NAMES.map((name) => {
    const source = resolveLicenseSourcePath(repoRoot, name);
    const destination = join(outDir, name);

    // `copyFileSync` carries the source's timestamps over to the copy with
    // nanosecond fidelity, so the published artefact keeps the canonical
    // licence revision's timestamp instead of an arbitrary build-time reading.
    copyFileSync(source, destination);

    const sourceStat = statSync(source);
    const sha256 = sha256File(source);
    const copiedSha256 = sha256File(destination);
    if (copiedSha256 !== sha256) {
      throw new Error(
        `Licence asset ${name} was altered while copying into the build output ` +
          `(source sha256 ${sha256}, copy sha256 ${copiedSha256}). Refusing to publish.`,
      );
    }

    return {
      name,
      source,
      destination,
      bytes: sourceStat.size,
      sha256,
      copiedSha256,
    };
  });
}

/**
 * Serves the licence assets as plain text ahead of the SPA fallback route.
 *
 * The middleware is installed before Vite's static file handler and before the
 * history-API fallback, so a request for `/LICENSE` is answered with the raw
 * file content instead of the single page application shell.
 */
export function createLicenseTextMiddleware(
  resolveAssets: () => Record<LicenseAssetName, string>,
) {
  return function licenseTextMiddleware(
    req: IncomingMessage,
    res: ServerResponse,
    next: (err?: unknown) => void,
  ): void {
    const rawUrl = req.url ?? "";
    const pathname = rawUrl.split("?")[0].split("#")[0];
    const name = LICENSE_ASSET_NAMES.find((asset) => pathname === `/${asset}`);

    if (!name) {
      next();
      return;
    }
    if (req.method !== "GET" && req.method !== "HEAD") {
      next();
      return;
    }

    const filePath = resolveAssets()[name];
    if (!existsSync(filePath)) {
      next();
      return;
    }

    const body = readFileSync(filePath);
    res.statusCode = 200;
    res.setHeader("Content-Type", "text/plain; charset=utf-8");
    res.setHeader("Content-Length", String(body.byteLength));
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("X-Content-Type-Options", "nosniff");

    if (req.method === "HEAD") {
      res.end();
      return;
    }
    res.end(body);
  };
}

/**
 * Vite plugin that publishes the canonical licence assets with the web bundle.
 *
 * - `closeBundle` copies the repository root files into the build output.
 * - `configureServer` / `configurePreviewServer` serve them as plain text so a
 *   direct request is never answered with the SPA shell.
 */
export function licenseAssetsPlugin(options: { repoRoot: string }): Plugin {
  const { repoRoot } = options;
  let outDir = "";

  return {
    name: "retailtwin:license-assets",

    configResolved(config) {
      // `build.outDir` is relative to the Vite root unless it is absolute.
      outDir = resolve(config.root, config.build.outDir);
    },

    closeBundle() {
      const results = copyLicenseAssets(repoRoot, outDir);
      for (const result of results) {
        this.info(
          `Licence asset ${result.name} published to ${result.destination} ` +
            `(${result.bytes} bytes, sha256 ${result.sha256})`,
        );
      }
    },

    configureServer(server) {
      server.middlewares.use(
        createLicenseTextMiddleware(() => licenseAssetPaths(repoRoot)),
      );
    },

    configurePreviewServer(server) {
      server.middlewares.use(
        createLicenseTextMiddleware(() => licenseAssetPaths(outDir)),
      );
    },
  };
}
