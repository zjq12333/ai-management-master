import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig(async () => ({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "@tauri-apps/api/core": path.resolve(__dirname, "./node_modules/@tauri-apps/api/src/core.ts"),
      "@tauri-apps/api/app": path.resolve(__dirname, "./node_modules/@tauri-apps/api/src/app.ts"),
      "@tauri-apps/api/window": path.resolve(__dirname, "./node_modules/@tauri-apps/api/src/window.ts"),
    },
  },
  clearScreen: false,
  server: {
    // Dev-only port — keep in sync with tauri.conf.json `devUrl`.
    port: 3123,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 3124,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
}));
