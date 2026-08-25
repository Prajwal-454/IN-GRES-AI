import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon-16x16.png", "apple-touch-icon.png"],
      manifest: {
        name: "IN-GRES AI",
        short_name: "IN-GRES",
        description:
          "Indian Groundwater Resource Estimation AI Virtual Assistant. Ask about groundwater resources using text or voice.",
        theme_color: "#075985",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        scope: "/",
        icons: [
          { src: "/pwa-192x192.png", sizes: "192x192", type: "image/png" },
          { src: "/pwa-512x512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg}"],
        navigateFallback: "/index.html",
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            urlPattern: /^https?:\/\/[^/]+\/api\/(?!auth\/)(?!push\/).*/,
            handler: "NetworkFirst",
            options: {
              cacheName: "ingres-api",
              networkTimeoutSeconds: 6,
              expiration: { maxEntries: 60, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/[^/]+\.(openstreetmap|tile)\.org\/.*/,
            handler: "StaleWhileRevalidate",
            options: {
              cacheName: "ingres-tiles",
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 },
            },
          },
        ],
      },
      devOptions: {
        enabled: true,
      },
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          axios: ["axios"],
          leaflet: ["leaflet"],
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
  server: {
    host: true,
    port: 5173,
    allowedHosts: [".trycloudflare.com", ".ngrok.io", ".ngrok-free.app", ".loca.lt", ".lhr.life"],
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});