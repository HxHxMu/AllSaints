import { defineConfig } from "astro/config";
import sitemap from "@astrojs/sitemap";

export default defineConfig({
  site: "https://allholysaints.com",
  trailingSlash: "always",
  integrations: [sitemap()],
  build: { inlineStylesheets: "always" },
  vite: { server: { fs: { allow: [".."] } } },
});
