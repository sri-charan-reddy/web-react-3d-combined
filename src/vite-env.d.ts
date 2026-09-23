/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Override the API origin when the UI is hosted apart from the backend. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
