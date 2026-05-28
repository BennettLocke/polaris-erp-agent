import type { AuthUser } from "@/types";

export function hasPermission(user: AuthUser | null | undefined, permission: string) {
  if (!user) return false;
  if (Number(user.is_admin || 0) === 1) return true;
  if (permission === "设置" && user.role === "admin") return true;
  return Array.isArray(user.permissions) && user.permissions.includes(permission);
}
