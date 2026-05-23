/**
 * Central API configuration.
 *
 * Set VITE_API_URL in a .env file (or your deployment environment) to point
 * at the backend.  Falls back to localhost:8000 for local development.
 *
 * Example .env:
 *   VITE_API_URL=https://api.gmf-investments.example.com
 */
const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default BASE_URL;
