let csrf: { token: string; headerName: string } | null = null;
export async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const method = options.method || "GET";
  if (!["GET", "HEAD"].includes(method) && !csrf)
    csrf = await request("/api/auth/csrf");
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD"].includes(method) && csrf)
    headers.set(csrf.headerName, csrf.token);
  let response: Response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
      credentials: "same-origin",
    });
  } catch {
    throw new Error(
      "The gateway is unreachable. Check that Spring Boot is running.",
    );
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      message = body.error?.message || message;
    } catch {
      /* sanitized transport error */
    }
    if (response.status === 403) csrf = null;
    throw new Error(message);
  }
  if (response.status === 204) return undefined as T;
  if (response.headers.get("Content-Type")?.includes("audio/"))
    return (await response.blob()) as T;
  return response.json();
}
export const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });
export function clearCsrf() {
  csrf = null;
}
