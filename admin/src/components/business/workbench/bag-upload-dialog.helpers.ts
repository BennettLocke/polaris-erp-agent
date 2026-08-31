import type { BagType } from "@/types";

export const BAG_TYPES: BagType[] = ["岩茶", "红茶", "宽版"];
const DEFAULT_PRICES: Record<BagType, string> = { 岩茶: "18", 红茶: "10", 宽版: "18" };

export type BagUploadPhase = "idle" | "uploading" | "complete" | "uncertain";
type BagUploadForm = { bagType: BagType; price: string; isListed: boolean };
type ArchiveFile = { name: string; size: number };
type Submission = {
  phase: BagUploadPhase;
  price: string;
  archive: ArchiveFile | null;
  archiveBytes: number | null;
};

export function initialBagUploadForm(): BagUploadForm {
  return { bagType: "岩茶", price: DEFAULT_PRICES.岩茶, isListed: true };
}

export function changeBagType(form: BagUploadForm, value: string): BagUploadForm {
  if (!BAG_TYPES.includes(value as BagType) || form.bagType === value) return form;
  const bagType = value as BagType;
  return { ...form, bagType, price: DEFAULT_PRICES[bagType] };
}

export function isValidBagPrice(price: string) {
  return /^\d{1,10}(?:\.\d{1,2})?$/.test(price) && Number(price) > 0 && Number(price) <= 9999999999.99;
}

export function validateBagArchive(file: ArchiveFile | null, archiveBytes: number | null): string {
  if (!file) return "请选择 ZIP 文件";
  if (!/\.zip$/i.test(file.name)) return "仅支持 ZIP 文件";
  if (!Number.isFinite(file.size) || file.size <= 0) return "ZIP 文件不能为空";
  if (!archiveBytes || !Number.isFinite(archiveBytes) || archiveBytes <= 0) return "尚未获取上传大小限制";
  if (file.size > archiveBytes) return `ZIP 超过大小限制（${formatBagFileSize(archiveBytes)}）`;
  return "";
}

export function formatBagFileSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

export function canStartBagUpload(submission: Submission) {
  return submission.phase === "idle" && isValidBagPrice(submission.price) && !validateBagArchive(submission.archive, submission.archiveBytes);
}

export function claimBagUpload(lock: { current: boolean }, submission: Submission) {
  if (lock.current || !canStartBagUpload(submission)) return false;
  lock.current = true;
  return true;
}
