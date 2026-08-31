import axios from "axios";

/**
 * Where the API lives.
 *
 * Worked out from wherever the app is being served, so one build works in
 * development and on the server without anybody editing this file: opened at
 * http://192.168.157.55:2025 it talks to http://192.168.157.55:9002/api, and
 * opened at http://localhost:5173 it talks to http://localhost:9002/api.
 *
 * Set VITE_API_BASE_URL in .env to override - a developer pointing at the
 * shared backend, or a deployment that proxies the API under the same origin
 * (VITE_API_BASE_URL=/api), which removes the cross-origin request altogether.
 */
const API_PORT = "9002";

const resolveBaseURL = (): string => {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured) return configured.replace(/\/+$/, "");

  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:${API_PORT}/api`;
};

const instance = axios.create({
  baseURL: resolveBaseURL(),
  headers: {
    "Content-Type": "application/json",
  },
});

export default instance;
