import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, Printer, X } from "lucide-react";

import { api } from "@/api";
import { Button } from "@/components/ui/button";
import type { SalesPrintTask } from "@/types";

type PrintFeedbackKind = "pending" | "printed" | "failed" | "timeout";

type PrintFeedbackState = {
  kind: PrintFeedbackKind;
  title: string;
  message: string;
  task?: SalesPrintTask;
};

const pollDelayMs = 1400;
const maxPollAttempts = 12;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function printTaskId(task?: SalesPrintTask | null) {
  return Number(task?.task_id || task?.id || 0);
}

function printTaskLabel(task?: SalesPrintTask | null) {
  return [task?.sales_no, task?.customer_name].filter(Boolean).join(" · ") || task?.job_no || "";
}

function feedbackForTask(task: SalesPrintTask): PrintFeedbackState | null {
  const status = String(task.status || "").toLowerCase();
  const label = printTaskLabel(task);
  if (status === "printed") {
    return {
      kind: "printed",
      title: "已发送到打印机",
      message: label ? `${label} 已由本地打印程序处理。` : "本地打印程序已处理这次打印任务。",
      task
    };
  }
  if (status === "failed") {
    return {
      kind: "failed",
      title: "打印失败",
      message: label ? `${label} 打印失败，请检查 sjAutoPrint 和打印机。` : "请检查 sjAutoPrint 和打印机。",
      task
    };
  }
  return null;
}

function useSalesPrintFeedback() {
  const [busySalesId, setBusySalesId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<PrintFeedbackState | null>(null);
  const runIdRef = useRef(0);

  useEffect(() => () => {
    runIdRef.current += 1;
  }, []);

  const closeFeedback = useCallback(() => {
    setFeedback(null);
  }, []);

  const pollTask = useCallback(async (taskId: number, runId: number, initialTask: SalesPrintTask) => {
    for (let attempt = 0; attempt < maxPollAttempts; attempt += 1) {
      await sleep(pollDelayMs);
      if (runIdRef.current !== runId) return;
      try {
        const task = await api.salesPrintTaskStatus(taskId);
        if (runIdRef.current !== runId) return;
        const resolved = feedbackForTask(task);
        if (resolved) {
          setFeedback(resolved);
          return;
        }
      } catch (err) {
        if (runIdRef.current !== runId) return;
        setFeedback({
          kind: "failed",
          title: "打印状态查询失败",
          message: err instanceof Error ? err.message : "无法读取打印任务状态。",
          task: initialTask
        });
        return;
      }
    }
    if (runIdRef.current !== runId) return;
    setFeedback({
      kind: "timeout",
      title: "本地打印程序暂未接收",
      message: "任务已创建，但还没有变成已打印。请确认 sjAutoPrint 已启动。",
      task: initialTask
    });
  }, []);

  const printSales = useCallback(async (salesId: number) => {
    if (!salesId) return null;
    const runId = runIdRef.current + 1;
    runIdRef.current = runId;
    setBusySalesId(salesId);
    setFeedback({
      kind: "pending",
      title: "打印任务已提交",
      message: "正在创建打印任务，稍后会自动检查本地打印程序是否接收。"
    });
    try {
      const task = await api.createSalesPrintTask(salesId);
      const taskId = printTaskId(task);
      setFeedback({
        kind: "pending",
        title: "打印任务已提交",
        message: taskId
          ? "任务已进入队列，等待本地打印程序处理。"
          : "任务已提交，但没有返回任务编号，请查看销售单打印状态。",
        task
      });
      if (taskId) {
        void pollTask(taskId, runId, task);
      }
      return task;
    } catch (err) {
      setFeedback({
        kind: "failed",
        title: "打印任务创建失败",
        message: err instanceof Error ? err.message : "请稍后重试。"
      });
      throw err;
    } finally {
      if (runIdRef.current === runId) {
        setBusySalesId(null);
      }
    }
  }, [pollTask]);

  return {
    busySalesId,
    feedback,
    closeFeedback,
    printSales
  };
}

type PrintFeedbackToastProps = {
  feedback: PrintFeedbackState | null;
  onClose: () => void;
};

function PrintFeedbackToast({ feedback, onClose }: PrintFeedbackToastProps) {
  if (!feedback) return null;
  const Icon = feedback.kind === "printed"
    ? CheckCircle2
    : feedback.kind === "failed" || feedback.kind === "timeout"
      ? AlertTriangle
      : Loader2;
  return (
    <div className={`print-feedback-toast print-feedback-toast--${feedback.kind}`} role="status" aria-live="polite">
      <div className="print-feedback-icon">
        <Icon className={feedback.kind === "pending" ? "print-feedback-spin" : undefined} />
      </div>
      <div className="print-feedback-body">
        <strong>{feedback.title}</strong>
        <p>{feedback.message}</p>
        {feedback.task?.job_no ? <span>任务号：{feedback.task.job_no}</span> : null}
      </div>
      <Button type="button" variant="ghost" size="icon-sm" aria-label="关闭打印提示" onClick={onClose}>
        <X />
      </Button>
    </div>
  );
}

export { PrintFeedbackToast, useSalesPrintFeedback };
