import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";
import { privateRoutes, precachePatterns } from "./src/pwaPolicy";
export default defineConfig({
  plugins: [
    vue(),
    VitePWA({
      registerType: "prompt",
      injectRegister: null,
      includeAssets: [
        "favicon.svg",
        "pwa-192.png",
        "pwa-512.png",
        "offline.html",
      ],
      manifest: {
        name: "贊耀服務平台",
        short_name: "贊耀服務平台",
        description: "贊耀電腦｜銷售・維修・資訊服務",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#f4f7fb",
        theme_color: "#0f172a",
        icons: [
          {
            src: "/pwa-192.png",
            sizes: "192x192",
            type: "image/png",
            purpose: "any",
          },
          {
            src: "/pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "any maskable",
          },
        ],
      },
      workbox: {
        cleanupOutdatedCaches: true,
        globPatterns: precachePatterns,
        navigateFallback: "index.html",
        navigateFallbackDenylist: privateRoutes,
        runtimeCaching: [],
      },
    }),
  ],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/attachments": "http://127.0.0.1:8000",
      "/reports": "http://127.0.0.1:8000",
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
