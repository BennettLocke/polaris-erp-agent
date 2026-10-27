import type { CustomerItem, SalesOrderPayload } from "@/types";
import type { SalesFormLine } from "./types";

export type SalesDraft = {
  selectedCustomer: CustomerItem | null;
  customerKeyword: string;
  productKeyword: string;
  lines: SalesFormLine[];
  defaultWarehouseId: number;
  lineQty: number;
  createTime: string;
  payStatus: SalesOrderPayload["pay_status"];
  payType: string;
};

type DraftStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type DraftSnapshot = {
  draft: SalesDraft;
  hasDraft: boolean;
  storageAvailable: boolean;
  submitting: boolean;
  needsSubmissionReview: boolean;
};
type FieldUpdate<T> = T | ((previous: T) => T);

export function salesDraftStorageKey(accountId: number) {
  return `polaris:sales-draft:v1:${accountId}`;
}

function positiveId(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) > 0;
}

function validNumber(value: unknown, minimum: number) {
  return typeof value === "number" && Number.isFinite(value) && value >= minimum;
}

function validDraft(value: unknown): value is SalesDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as SalesDraft;
  return (draft.selectedCustomer === null || (
    typeof draft.selectedCustomer === "object" && positiveId(draft.selectedCustomer?.id)
  ))
    && typeof draft.customerKeyword === "string"
    && typeof draft.productKeyword === "string"
    && typeof draft.createTime === "string"
    && (draft.createTime === "" || /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(draft.createTime))
    && ["paid", "monthly", "unpaid"].includes(draft.payStatus)
    && typeof draft.payType === "string"
    && positiveId(draft.defaultWarehouseId)
    && validNumber(draft.lineQty, Number.MIN_VALUE)
    && Array.isArray(draft.lines)
    && draft.lines.every((line) => line && positiveId(line.product_id)
      && positiveId(line.unit_id) && positiveId(line.warehouse_id)
      && typeof line.title === "string" && typeof line.spec === "string"
      && validNumber(line.buy_number, Number.MIN_VALUE) && validNumber(line.price, 0));
}

export function createSalesDraftSession(
  accountId: number,
  defaults: () => SalesDraft,
  getStorage: () => DraftStorage = () => window.sessionStorage
) {
  const key = salesDraftStorageKey(accountId);
  const listeners = new Set<() => void>();
  let revision = 0;
  let generation = 0;
  let closed = false;
  let storage: DraftStorage | undefined;
  let snapshot: DraftSnapshot = { draft: defaults(), hasDraft: false, storageAvailable: true, submitting: false, needsSubmissionReview: false };

  try {
    storage = getStorage();
    const raw = storage.getItem(key);
    if (raw !== null) {
      try {
        const saved = JSON.parse(raw);
        if (saved?.version !== 1 || saved.accountId !== accountId || !validDraft(saved.draft)) {
          throw new Error("Invalid sales draft");
        }
        snapshot = { ...snapshot, draft: saved.draft, hasDraft: true, needsSubmissionReview: saved.submissionPending === true };
      } catch {
        storage.removeItem(key);
      }
    }
  } catch {
    snapshot = { ...snapshot, storageAvailable: false };
  }

  function emit() {
    listeners.forEach((listener) => listener());
  }

  function persist() {
    try {
      if (!storage) throw new Error("Session storage unavailable");
      if (snapshot.hasDraft) {
        storage.setItem(key, JSON.stringify({ version: 1, accountId, draft: snapshot.draft, submissionPending: snapshot.submitting || snapshot.needsSubmissionReview }));
      } else {
        storage.removeItem(key);
      }
    } catch {
      snapshot = { ...snapshot, storageAvailable: false };
    }
  }

  return {
    getSnapshot: () => snapshot,
    getRevision: () => revision,
    getGeneration: () => generation,
    isCurrent: (expectedGeneration: number) => !closed && generation === expectedGeneration,
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => { listeners.delete(listener); };
    },
    setField<K extends keyof SalesDraft>(field: K, update: FieldUpdate<SalesDraft[K]>) {
      if (closed || snapshot.submitting || snapshot.needsSubmissionReview) return;
      const value = typeof update === "function" ? update(snapshot.draft[field]) : update;
      if (Object.is(value, snapshot.draft[field])) return;
      revision++;
      snapshot = { ...snapshot, draft: { ...snapshot.draft, [field]: value }, hasDraft: true };
      persist();
      emit();
    },
    initialize(patch: Partial<SalesDraft>, expectedRevision: number) {
      // Late default lookups must never replace restored or user-entered fields.
      if (closed || snapshot.hasDraft || revision !== expectedRevision || snapshot.submitting) return;
      snapshot = { ...snapshot, draft: { ...snapshot.draft, ...patch } };
      emit();
    },
    reset(next: SalesDraft = defaults()) {
      if (closed) return;
      revision++;
      generation++;
      snapshot = { ...snapshot, draft: next, hasDraft: false, needsSubmissionReview: false };
      persist();
      emit();
    },
    setSubmitting(submitting: boolean) {
      if (closed) return;
      snapshot = { ...snapshot, submitting };
      persist();
      emit();
    },
    acknowledgeSubmissionReview() {
      if (closed || snapshot.submitting) return;
      snapshot = { ...snapshot, needsSubmissionReview: false };
      persist();
      emit();
    },
    endSession() {
      revision++;
      generation++;
      closed = true;
      snapshot = { ...snapshot, draft: defaults(), hasDraft: false, submitting: true };
      persist();
      emit();
    }
  };
}

export type SalesDraftSession = ReturnType<typeof createSalesDraftSession>;
