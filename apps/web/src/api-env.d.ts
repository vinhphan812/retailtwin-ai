interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string;
  /** "true" lets a production build open `?twin=demo` (the hosted demo). */
  readonly VITE_ALLOW_DEMO?: string;
  /** The app version, shown in the footer. TODO(#165): from the canonical /VERSION. */
  readonly VITE_APP_VERSION?: string;
  /** Short Git SHA of the build, set by `vite.config.ts`. */
  readonly VITE_GIT_SHA?: string;
}
