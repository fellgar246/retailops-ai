// `server-only` exists to fail a build that imports server code into a client
// bundle. Under the test runner there is no such boundary, so it resolves to
// nothing.
export {};
