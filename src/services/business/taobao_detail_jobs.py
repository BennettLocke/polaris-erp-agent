"""Background jobs for Taobao detail-page export."""

from __future__ import annotations

import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from src.utils import get_logger

from .taobao_detail import TaobaoDetailExportResult, TaobaoDetailExportService


logger = get_logger("sjagent.taobao_detail_jobs")


@dataclass
class TaobaoDetailExportJob:
    job_id: str
    product_id: int
    status: str = "pending"
    message: str = "等待生成"
    filename: str = ""
    html_filename: str = ""
    taobao_title: str = ""
    error: str = ""
    main_image: dict | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    completed_at: float = 0
    content: bytes | None = None

    def snapshot(self, *, include_download_url: bool = True) -> dict[str, Any]:
        data = {
            "job_id": self.job_id,
            "product_id": self.product_id,
            "status": self.status,
            "message": self.message,
            "filename": self.filename,
            "html_filename": self.html_filename,
            "taobao_title": self.taobao_title,
            "error": self.error,
            "created_at": int(self.created_at),
            "updated_at": int(self.updated_at),
            "completed_at": int(self.completed_at or 0),
        }
        if include_download_url and self.status == "completed":
            data["download_url"] = f"/api/product/taobao-detail-export/jobs/{self.job_id}/download"
        return data


class TaobaoDetailExportJobManager:
    def __init__(
        self,
        *,
        max_workers: int = 2,
        ttl_seconds: int = 30 * 60,
        max_completed_jobs: int = 50,
    ):
        self.ttl_seconds = max(60, int(ttl_seconds or 1800))
        self.max_completed_jobs = max(5, int(max_completed_jobs or 50))
        self._executor = ThreadPoolExecutor(max_workers=max(1, int(max_workers or 2)))
        self._lock = Lock()
        self._jobs: dict[str, TaobaoDetailExportJob] = {}

    def start(self, product_id: int, main_image: dict | None = None) -> TaobaoDetailExportJob:
        self._cleanup()
        job = TaobaoDetailExportJob(
            job_id=f"tdx-{int(time.time())}-{uuid.uuid4().hex[:10]}",
            product_id=int(product_id),
            status="pending",
            message="已加入后台生成队列",
            main_image=main_image,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._executor.submit(self._run_job, job.job_id)
        return self.get(job.job_id) or job

    def get(self, job_id: str) -> TaobaoDetailExportJob | None:
        self._cleanup()
        with self._lock:
            return self._jobs.get(str(job_id or "").strip())

    def download(self, job_id: str) -> TaobaoDetailExportResult | None:
        job = self.get(job_id)
        if not job or job.status != "completed" or job.content is None:
            return None
        return TaobaoDetailExportResult(
            filename=job.filename,
            content=job.content,
            template_image_urls=[],
            detail_image_urls=[],
            dimensions={},
            html_filename=job.html_filename,
            taobao_title=job.taobao_title,
        )

    def _run_job(self, job_id: str) -> None:
        self._update(job_id, status="running", message="正在生成淘宝详情页资料包")
        try:
            job = self._job(job_id)
            result = TaobaoDetailExportService().export_zip(self._job_product_id(job_id), main_image=job.main_image)
            self._update(
                job_id,
                status="completed",
                message="淘宝详情页资料包已生成",
                filename=result.filename,
                html_filename=result.html_filename,
                taobao_title=result.taobao_title,
                content=result.content,
                main_image=None,
                completed_at=time.time(),
            )
        except Exception as exc:
            logger.error(f"淘宝详情页后台导出失败: job_id={job_id}, error={exc}")
            self._update(
                job_id,
                status="failed",
                message="淘宝详情页资料包生成失败",
                error=str(exc),
                main_image=None,
                completed_at=time.time(),
            )

    def _job_product_id(self, job_id: str) -> int:
        with self._lock:
            job = self._jobs[job_id]
            return int(job.product_id)

    def _job(self, job_id: str) -> TaobaoDetailExportJob:
        with self._lock:
            return self._jobs[job_id]

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            removable = [
                job_id
                for job_id, job in self._jobs.items()
                if job.status in {"completed", "failed"} and (now - (job.completed_at or job.updated_at)) > self.ttl_seconds
            ]
            for job_id in removable:
                self._jobs.pop(job_id, None)

            completed_ids = [
                job_id
                for job_id, job in sorted(self._jobs.items(), key=lambda item: item[1].updated_at)
                if job.status in {"completed", "failed"}
            ]
            overflow = len(completed_ids) - self.max_completed_jobs
            for job_id in completed_ids[:max(0, overflow)]:
                self._jobs.pop(job_id, None)


_job_manager: TaobaoDetailExportJobManager | None = None


def get_taobao_detail_export_job_manager() -> TaobaoDetailExportJobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = TaobaoDetailExportJobManager()
    return _job_manager
