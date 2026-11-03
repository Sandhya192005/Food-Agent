import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server forwards /api calls to the FastAPI backend, so the browser
// sees one origin and the backend needs no CORS setup for local development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
