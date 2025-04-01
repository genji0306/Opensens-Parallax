/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string
  readonly VITE_APP_NAME: string
  readonly VITE_APP_VERSION: string
  readonly VITE_APP_DESCRIPTION: string
  readonly VITE_APP_AUTHOR: string
  readonly VITE_APP_LICENSE: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
} 