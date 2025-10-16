// Minimal browser shim for `googleapis` to avoid bundling Node-only code in the client.
// Any direct calls will throw with a clear message. Use backend endpoints for Google API operations.

export const google = new Proxy({}, {
  get() {
    throw new Error('googleapis is not available in the browser. Use server endpoints for Google OAuth/Calendar.');
  }
}) as any;

export default { google } as any;
