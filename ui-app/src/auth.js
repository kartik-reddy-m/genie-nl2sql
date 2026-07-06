// Google Sign-In token handling for the SPA.
// If VITE_GOOGLE_CLIENT_ID is empty, auth is DISABLED (local dev) and the app
// runs without a login gate — matching the backend's behavior.

const TOKEN_KEY = "genie_id_token";

export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";
export const authEnabled = !!GOOGLE_CLIENT_ID;

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

function decodeJwt(token) {
  try {
    const payload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(decodeURIComponent(escape(atob(payload))));
  } catch {
    return null;
  }
}

// Returns the current signed-in user (from the stored token), or null.
// Clears the token if it has expired.
export function getUser() {
  const token = getToken();
  if (!token) return null;
  const p = decodeJwt(token);
  if (!p) {
    setToken("");
    return null;
  }
  if (p.exp && p.exp * 1000 < Date.now()) {
    setToken("");
    return null;
  }
  return { email: p.email, name: p.name, picture: p.picture, exp: p.exp };
}

export function signOut() {
  setToken("");
  if (window.google?.accounts?.id) {
    window.google.accounts.id.disableAutoSelect();
  }
}
