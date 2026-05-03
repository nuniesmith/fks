import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
    plugins: [sveltekit()],
    server: {
        proxy: {
            "/api": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            "/sse": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            "/bars": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            "/factory": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            "/kraken": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            "/health": {
                target: "http://fks_ruby:8000",
                changeOrigin: true,
            },
            // Futures FastAPI — proxy /fapi/* → http://fks_ruby:8080/*
            // e.g. /fapi/api/dashboard → http://fks_ruby:8080/api/dashboard
            "/fapi": {
                target: "http://fks_ruby:8080",
                changeOrigin: true,
                rewrite: (path) => path.replace(/^\/fapi/, ""),
            },
        },
    },
});
