/// <reference types="vite/client" />

interface ImportMetaEnv {
	readonly VITE_DATA_QUERY_API_URL?: string;
	readonly VITE_DATA_QUERY_API_KEY?: string;
}

interface ImportMeta {
	readonly env: ImportMetaEnv;
}
