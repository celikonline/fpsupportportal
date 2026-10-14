export type User = { id: number; name: string; username: string };
export type Tenant = {
  id: string;
  name: string;
  role: string;
  retentionDays: number;
  retentionApproved: boolean;
};
export type Project = {
  id: string;
  name: string;
  code: string;
  role: string;
  archived: boolean;
  timezone: string;
  firstResponseMinutes: number;
  resolutionMinutes: number;
  businessStart: number;
  businessEnd: number;
  holidays: string[];
  categories: string[];
};
export type Attachment = {
  id: string;
  filename: string;
  mimeType: string;
  size: number;
  state: string;
  reason: string;
};
export type Comment = {
  id: string;
  body: string;
  visibility: string;
  source?: "human" | "customer_agent" | "external_agent";
  author: User;
  createdAt: string;
  attachments: Attachment[];
};
export type Ticket = {
  id: string;
  number: string;
  title: string;
  description: string;
  category: string;
  priority: string;
  status: string;
  version: number;
  requester: User;
  assignee: User | null;
  createdAt: string;
  updatedAt: string;
  firstResponseDue: string;
  resolutionDue: string;
  slaRisk: boolean;
  tags: string[];
  legalHold: boolean;
  attachments: Attachment[];
  comments: Comment[];
  events: {
    id: string;
    action: string;
    detail: string;
    reason: string;
    createdAt: string;
  }[];
};
export type TicketPage = {
  results: Ticket[];
  total: number;
  page: number;
  pageSize: number;
  stats: { open: number; waiting: number; resolved: number };
};
let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRFToken", csrf);
  const response = await fetch("/api/v1/" + path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  const result = await response
    .json()
    .catch(() => ({ detail: "Sunucu yanıtı okunamadı." }));
  if (!response.ok) {
    if (result.authenticationRequired && typeof window !== "undefined")
      window.dispatchEvent(new Event("fp-session-expired"));
    throw new Error(result.detail || "İşlem tamamlanamadı.");
  }
  return result as T;
}
export function command<T>(
  path: string,
  body: unknown,
  key: string = crypto.randomUUID(),
) {
  return api<T>(path, {
    method: "POST",
    headers: { "Idempotency-Key": key },
    body: JSON.stringify(body),
  });
}
export const statuses: Record<string, string> = {
  new: "Yeni",
  triaged: "Değerlendirildi",
  in_progress: "İşlemde",
  waiting_requester: "Yanıt bekleniyor",
  waiting_internal: "İç ekip bekleniyor",
  resolved: "Çözüldü",
  closed: "Kapandı",
  cancelled: "İptal",
};
export const priorities: Record<string, string> = {
  low: "Düşük",
  normal: "Normal",
  high: "Yüksek",
  critical: "Kritik",
};
export const roles: Record<string, string> = {
  manager: "Proje yöneticisi",
  lead: "Destek lideri",
  agent: "Destek uzmanı",
  requester: "Talep sahibi",
  observer: "Gözlemci",
};
export function date(value: string) {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
export function bytes(value: number) {
  return value < 1024 * 1024
    ? `${Math.ceil(value / 1024)} KB`
    : `${(value / 1024 / 1024).toFixed(1)} MB`;
}
