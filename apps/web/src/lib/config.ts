/**
 * Where the browser sends API calls.
 *
 * Always this application's own origin: a server-side route attaches the
 * credential and forwards the request. Nothing about the API's real location is
 * baked into the bundle, so one image runs in every environment.
 */
export const API_BASE_URL = '/api/proxy';
