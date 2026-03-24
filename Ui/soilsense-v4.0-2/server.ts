import express from "express";
import { createServer as createViteServer } from "vite";
import path from "path";
import { fileURLToPath } from "url";
import httpProxy from "http-proxy";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function startServer() {
  const app = express();
  const PORT = 3000;
  const PYTHON_API_URL = "http://localhost:5001";
  const proxy = httpProxy.createProxyServer();

  app.use(express.json());

  // Proxy all /api requests to the Python Logic Engine
  app.all("/api/*", (req, res) => {
    proxy.web(req, res, { target: PYTHON_API_URL }, (e) => {
      res.status(502).json({ 
        error: "Python Logic Engine Offline", 
        message: "Ensure hardware_api.py is running on port 5001" 
      });
    });
  });

  // Vite middleware for development
  const isProd = process.env.NODE_ENV === "production";
  if (!isProd) {
    console.log("Starting in DEVELOPMENT mode with Vite middleware");
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    console.log("Starting in PRODUCTION mode serving static files");
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`SoilSense UI Host running on http://localhost:${PORT}`);
    console.log(`Proxying API calls to ${PYTHON_API_URL}`);
  });
}

startServer();
