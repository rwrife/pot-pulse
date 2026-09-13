import { defineConfig } from "vite";

export default defineConfig({
  // Served from the device or opened from any static path.
  base: "./",
  build: {
    target: "es2022",
  },
});
