let csrf = "";
export class ApiError extends Error {
  constructor(
    public status: number,
    public data: any,
  ) {
    super(data?.message || data?.detail || "無法完成操作");
  }
}
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRFToken", csrf);
  let response: Response;
  try {
    response = await fetch("/api/" + path, {
      ...options,
      headers,
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, {
      message: "網路連線中斷，資料尚未送出。請恢復連線後再試。",
    });
  }
  const data = await response
    .json()
    .catch(() => ({ message: "伺服器回應不正確，請稍後重試" }));
  if (data.csrf_token) csrf = data.csrf_token;
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("session-expired"));
    if (data.code === "password_change_required")
      window.dispatchEvent(new Event("password-required"));
    throw new ApiError(response.status, data);
  }
  return data;
}
export const post = <T = any>(path: string, data: any) =>
  api<T>(path, {
    method: "POST",
    body: data instanceof FormData ? data : JSON.stringify(data),
  });
export function errorText(e: any): string {
  const fields = e?.data?.fields;
  return fields
    ? Object.values(fields).flat().join("；")
    : e.message || "操作失敗";
}
export function dateText(value: string) {
  return value
    ? new Intl.DateTimeFormat("zh-TW", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(new Date(value))
    : "—";
}
