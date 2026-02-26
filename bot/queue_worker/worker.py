"""
Async job queue for video processing.
Uses asyncio.Queue + semaphore for concurrency control.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Optional

from bot.config import MAX_CONCURRENT_JOBS, MAX_USER_QUEUE, RATE_LIMIT_PER_MIN, TEMP_DIR, TG_UPLOAD_LIMIT
from bot.i18n import t as _t

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING    = auto()
    PROCESSING = auto()
    DONE       = auto()
    FAILED     = auto()
    CANCELLED  = auto()


@dataclass
class Job:
    id:          str
    user_id:     int
    input_path:  str
    settings:    Any          # UserSettings
    chat_id:     int
    message_id:  int
    copies:      int   = 1    # сколько уникальных копий сделать
    variation:   int   = 0    # разброс интенсивности ±%, 0=выкл
    created_at:  float = field(default_factory=time.time)
    status:      JobStatus = JobStatus.PENDING
    result:      Optional[dict] = None
    error:       Optional[str]  = None
    progress:    float = 0.0
    progress_msg: str = ""


# ── Rate limiter ───────────────────────────────────────────────────────────────

class RateLimiter:
    def __init__(self, max_per_minute: int):
        self.max   = max_per_minute
        self._log: dict[int, list[float]] = {}

    def check(self, user_id: int) -> bool:
        """Returns True if user is within rate limit."""
        now = time.time()
        window = 60.0
        log = self._log.setdefault(user_id, [])
        # Purge old
        self._log[user_id] = [t for t in log if now - t < window]
        if len(self._log[user_id]) >= self.max:
            return False
        self._log[user_id].append(now)
        return True

    def seconds_until_free(self, user_id: int) -> float:
        now = time.time()
        log = self._log.get(user_id, [])
        if not log:
            return 0.0
        oldest = min(log)
        return max(0.0, 60.0 - (now - oldest))


# ── Queue manager ──────────────────────────────────────────────────────────────

class VideoQueue:
    def __init__(self):
        self._queue:     asyncio.Queue[Job] = asyncio.Queue()
        self._sem:       asyncio.Semaphore  = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
        self._jobs:      dict[str, Job]     = {}
        self._user_jobs: dict[int, list[str]] = {}  # user_id → list of active job_ids
        self._rate:      RateLimiter        = RateLimiter(RATE_LIMIT_PER_MIN)
        self._running:   bool               = False
        self._bot:       Any                = None  # set on start

    def set_bot(self, bot) -> None:
        self._bot = bot

    # ── Public API ─────────────────────────────────────────────────────────────

    def check_rate(self, user_id: int) -> tuple[bool, float]:
        ok = self._rate.check(user_id)
        wait = self._rate.seconds_until_free(user_id) if not ok else 0.0
        return ok, wait

    def user_active_jobs(self, user_id: int) -> list[Job]:
        """Return list of active (PENDING/PROCESSING) jobs, auto-expiring stuck ones."""
        job_ids = self._user_jobs.get(user_id, [])
        active: list[Job] = []
        for job_id in job_ids:
            job = self._jobs.get(job_id)
            if job is None or job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
                continue
            age = time.time() - job.created_at
            if job.status == JobStatus.PROCESSING and age > 600:
                logger.warning(f"Force-expiring stuck PROCESSING job {job.id} (age={age:.0f}s)")
                job.status = JobStatus.FAILED
                job.error = "Timeout: job took too long"
                continue
            if job.status == JobStatus.PENDING and age > 300:
                logger.warning(f"Force-expiring stuck PENDING job {job.id} (age={age:.0f}s)")
                job.status = JobStatus.FAILED
                job.error = "Timeout: job stuck in queue"
                continue
            active.append(job)
        return active

    def user_queue_full(self, user_id: int) -> bool:
        return len(self.user_active_jobs(user_id)) >= MAX_USER_QUEUE

    def user_active_job_count(self, user_id: int) -> int:
        return len(self.user_active_jobs(user_id))

    def user_has_active_job(self, user_id: int) -> bool:
        return self.user_active_job_count(user_id) > 0

    def get_user_jobs(self, user_id: int) -> list[Job]:
        return self.user_active_jobs(user_id)

    def get_user_job(self, user_id: int) -> Optional[Job]:
        jobs = self.get_user_jobs(user_id)
        return jobs[0] if jobs else None

    def queue_size(self) -> int:
        return self._queue.qsize()

    def total_pending(self) -> int:
        return sum(
            1 for j in self._jobs.values()
            if j.status == JobStatus.PENDING
        )

    async def enqueue(
        self,
        user_id:    int,
        input_path: str,
        settings,
        chat_id:    int,
        message_id: int,
        copies:     int = 1,
        variation:  int = 0,
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            user_id=user_id,
            input_path=input_path,
            settings=settings,
            chat_id=chat_id,
            message_id=message_id,
            copies=copies,
            variation=variation,
        )
        self._jobs[job.id] = job
        self._user_jobs.setdefault(user_id, []).append(job.id)
        await self._queue.put(job)
        logger.info(f"Enqueued job {job.id} for user {user_id}")
        return job

    def cancel_job(self, job_id: str, user_id: int) -> bool:
        """Cancel a specific job by ID if it belongs to user and is PENDING."""
        job = self._jobs.get(job_id)
        if job and job.user_id == user_id and job.status == JobStatus.PENDING:
            job.status = JobStatus.CANCELLED
            return True
        return False

    def cancel_all_user_jobs(self, user_id: int) -> int:
        """Cancel all PENDING jobs for user. Returns count cancelled."""
        cancelled = 0
        for job in self.user_active_jobs(user_id):
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                cancelled += 1
        return cancelled

    def cancel_user_job(self, user_id: int) -> bool:
        """Legacy: cancel first pending job."""
        for job in self.user_active_jobs(user_id):
            if job.status == JobStatus.PENDING:
                job.status = JobStatus.CANCELLED
                return True
        return False

    # ── Worker loop ────────────────────────────────────────────────────────────

    async def start(self, bot=None) -> None:
        self._bot     = bot
        self._running = True
        asyncio.create_task(self._worker_loop())
        asyncio.create_task(self._temp_cleanup_loop())
        logger.info("VideoQueue worker started")

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if job.status == JobStatus.CANCELLED:
                self._queue.task_done()
                continue

            asyncio.create_task(self._process_job(job))

    async def _temp_cleanup_loop(self) -> None:
        """Periodically clean up old temp files (every 10 minutes)."""
        while self._running:
            await asyncio.sleep(600)  # 10 min
            try:
                await _cleanup_temp_dir()
            except Exception as e:
                logger.error(f"Temp cleanup error: {e}")

    async def _process_job(self, job: Job) -> None:
        async with self._sem:
            await self._run_job(job)

    async def _run_job(self, job: Job) -> None:
        from bot.processors.pipeline import process_video, build_report, ProcessingError

        job.status = JobStatus.PROCESSING
        logger.info(f"Processing job {job.id} copies={job.copies} for user {job.user_id}")

        copies    = max(1, job.copies)
        variation = job.variation
        lang      = job.settings.language

        # Upload limit: 2 GB with local API server, 49 MB with standard Telegram
        TG_MAX_FILE_SIZE = TG_UPLOAD_LIMIT

        copy_status = [_t("worker_waiting", lang)] * copies
        _last_update = [0.0]

        async def update_progress_msg(copy_idx: int, pct: float, msg: str = "") -> None:
            if not self._bot or not job.message_id:
                return
            now = time.time()
            if pct < 1.0 and now - _last_update[0] < 3.0:
                copy_status[copy_idx] = f"{_make_bar(pct)} {int(pct*100)}%"
                return
            _last_update[0] = now
            try:
                bar = _make_bar(pct)
                copy_status[copy_idx] = f"{bar} {int(pct*100)}%  {_stage_label(pct, msg, lang)}"

                copies_word = _t("worker_copies_word", lang, n=copies) if copies == 1 else _t("worker_copies_word_plural", lang, n=copies)
                lines = [_t("worker_processing", lang, copies=copies_word)]
                for i, st in enumerate(copy_status):
                    prefix = "▶️" if i == copy_idx else ("✅" if "100%" in st else "⬜")
                    lines.append(f"{prefix} {_t('worker_copy_of', lang, i=i+1, n=copies)}:  {st}")

                await self._bot.edit_message_text(
                    text="\n".join(lines),
                    chat_id=job.chat_id,
                    message_id=job.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

        completed_paths: list[str] = []
        completed_results: list[tuple[int, dict]] = []  # (copy_index, result)
        all_hashes_unique = True
        seen_hashes: set[str] = set()
        send_failed = False  # track if any send to user failed
        _copy_lock = asyncio.Lock()  # protect shared state in parallel processing

        # Parallel processing: up to 3 copies at once
        MAX_PARALLEL_COPIES = 3
        copy_sem = asyncio.Semaphore(MAX_PARALLEL_COPIES)

        async def _process_one_copy(i: int) -> None:
            nonlocal all_hashes_unique, send_failed

            async with copy_sem:
                copy_status[i] = _t("worker_starting", lang)

                # Разброс интенсивности: клонируем настройки и случайно меняем intensity
                import copy as _copy
                import random
                cur_settings = _copy.deepcopy(job.settings)

                if variation > 0 and copies > 1:
                    rng = random.Random(i * 0xABCD1234)
                    for ms in cur_settings.methods.values():
                        if not ms.enabled:
                            continue
                        delta = rng.uniform(-variation, variation)
                        new_intensity = ms.intensity + delta
                        ms.intensity = max(1, min(100, round(new_intensity)))

                job_seed = random.randint(0, 2**32 - 1)

                async def progress_cb(pct: float, msg: str = "", _i=i) -> None:
                    await update_progress_msg(_i, pct, msg)

                result = await process_video(
                    input_path=job.input_path,
                    user_settings=cur_settings,
                    progress_cb=progress_cb,
                    job_seed=job_seed,
                )

                out_size = result.get("output_size", 0)
                if out_size < 1024:
                    logger.error(f"Job {job.id} copy {i+1}: output too small ({out_size} bytes), skipping")
                    _safe_remove(result["output_path"])
                    copy_status[i] = _t("worker_empty", lang)
                    return

                out_hash = result["output_hash_md5"]
                async with _copy_lock:
                    if out_hash in seen_hashes:
                        all_hashes_unique = False
                    seen_hashes.add(out_hash)
                    completed_paths.append(result["output_path"])
                    completed_results.append((i, result))

                copy_status[i] = _t("worker_done", lang, h=out_hash[:8])
                await update_progress_msg(i, 1.0)

                # Отправляем сразу если копий мало (≤4)
                if copies <= 4 and self._bot:
                    report = build_report(result, lang)
                    hash_note = _t("worker_hash_ok", lang) if result['input_hash_md5'] != out_hash else _t("worker_hash_same", lang)
                    caption = (
                        _t("report_copy_label", lang, i=i+1, n=copies, hash_note=hash_note) + "\n\n" + report
                    ) if copies > 1 else report
                    try:
                        from aiogram.types import FSInputFile
                        if out_size > TG_MAX_FILE_SIZE:
                            await self._bot.send_message(
                                chat_id=job.chat_id,
                                text=_t("worker_too_big", lang, i=i+1, size=f"{out_size/1024/1024:.0f}", limit=f"{TG_MAX_FILE_SIZE // (1024*1024)}"),
                                parse_mode="HTML",
                            )
                            send_failed = True
                        else:
                            doc = FSInputFile(
                                path=result["output_path"],
                                filename=f"copy_{i+1:02d}_{os.path.basename(result['output_path'])}",
                            )
                            await self._bot.send_document(
                                chat_id=job.chat_id,
                                document=doc,
                                caption=caption,
                                parse_mode="HTML",
                            )
                    except Exception as e:
                        logger.error(f"Failed to send copy {i+1}: {e}")
                        send_failed = True

        try:
            # Launch all copies in parallel (limited by semaphore)
            tasks = [asyncio.create_task(_process_one_copy(i)) for i in range(copies)]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Check for exceptions in tasks
            for i, task in enumerate(tasks):
                if task.exception():
                    logger.error(f"Job {job.id} copy {i+1} failed: {task.exception()}")
                    copy_status[i] = _t("worker_error", lang)

            job.status = JobStatus.DONE

            # Для 5+ копий — отправляем порциями (zip'ы до 49MB)
            if copies >= 5 and self._bot and completed_paths:
                await self._bot.edit_message_text(
                    text=_t("worker_sending", lang, n=len(completed_paths)),
                    chat_id=job.chat_id,
                    message_id=job.message_id,
                    parse_mode="HTML",
                )
                hash_note = _t("worker_all_unique", lang) if all_hashes_unique else _t("worker_some_same", lang)
                var_note = f"±{variation}%" if variation > 0 else _t("worker_var_off", lang)

                # Split into chunks that fit under Telegram limit
                zip_paths = await _create_chunked_zips(completed_paths, job.id, TG_MAX_FILE_SIZE)

                sent_count = 0
                for zi, zp in enumerate(zip_paths):
                    try:
                        from aiogram.types import FSInputFile
                        zip_size = os.path.getsize(zp)
                        if zip_size > TG_MAX_FILE_SIZE:
                            logger.error(f"Zip chunk {zi+1} still too large: {zip_size}")
                            send_failed = True
                            continue
                        part_label = _t("worker_part_label", lang, i=zi+1, n=len(zip_paths)) if len(zip_paths) > 1 else ""
                        doc = FSInputFile(path=zp, filename=f"uniqueluzer_{len(completed_paths)}copies{part_label}.zip")
                        await self._bot.send_document(
                            chat_id=job.chat_id,
                            document=doc,
                            caption=_t("worker_zip_done", lang, n=len(completed_paths), part=part_label, hash_note=hash_note, var=var_note),
                            parse_mode="HTML",
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send zip chunk {zi+1}: {e}")
                        send_failed = True
                    finally:
                        _safe_remove(zp)

                if sent_count == 0 and completed_paths:
                    send_failed = True
                    logger.warning(f"Job {job.id}: all zips failed, falling back to individual files")
                    for fi, fp in enumerate(completed_paths):
                        try:
                            from aiogram.types import FSInputFile
                            fsize = os.path.getsize(fp) if os.path.exists(fp) else 0
                            if fsize > TG_MAX_FILE_SIZE or fsize < 1024:
                                continue
                            doc = FSInputFile(path=fp, filename=f"copy_{fi+1:03d}.mp4")
                            await self._bot.send_document(
                                chat_id=job.chat_id,
                                document=doc,
                                caption=_t("worker_copy_of", lang, i=fi+1, n=len(completed_paths)),
                                parse_mode="HTML",
                            )
                            send_failed = False
                        except Exception:
                            pass

            # Обновляем/удаляем сообщение прогресса
            if self._bot:
                try:
                    if send_failed:
                        await self._bot.edit_message_text(
                            text=_t("worker_send_failed", lang, done=len(completed_paths), total=copies),
                            chat_id=job.chat_id,
                            message_id=job.message_id,
                            parse_mode="HTML",
                        )
                    else:
                        await self._bot.delete_message(
                            chat_id=job.chat_id,
                            message_id=job.message_id,
                        )
                except Exception:
                    pass

        except ProcessingError as e:
            job.status = JobStatus.FAILED
            job.error  = str(e)
            logger.warning(f"Job {job.id} failed: {e}")
            if self._bot:
                try:
                    await self._bot.edit_message_text(
                        text=_t("err_processing", lang, e=str(e)),
                        chat_id=job.chat_id,
                        message_id=job.message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error  = str(e)
            logger.exception(f"Unexpected error in job {job.id}")
            if self._bot:
                try:
                    await self._bot.edit_message_text(
                        text=_t("err_unexpected", lang, e=str(e)[:300]),
                        chat_id=job.chat_id,
                        message_id=job.message_id,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass

        finally:
            # Cleanup all output files
            for p in completed_paths:
                _safe_remove(p)
            _safe_remove(job.input_path)

            if job.status == JobStatus.DONE:
                job.settings.processed_total += copies
                job.settings.processed_today += copies
                job.settings.save()

            asyncio.create_task(_cleanup_job(self._jobs, self._user_jobs, job.id, job.user_id, delay=300))


async def _create_chunked_zips(
    paths: list[str], job_id: str, max_size: int = 49 * 1024 * 1024,
) -> list[str]:
    """Packs files into ZIP archive(s), each under max_size bytes.
    Returns list of zip file paths.
    """
    import zipfile
    loop = asyncio.get_event_loop()

    def _zip():
        result_paths: list[str] = []
        chunk_idx = 0
        current_size = 0
        current_files: list[tuple[str, str]] = []  # (src_path, archive_name)

        for i, p in enumerate(paths):
            if not os.path.exists(p):
                continue
            fsize = os.path.getsize(p)
            ext = os.path.splitext(p)[1]
            name = f"copy_{i+1:03d}{ext}"

            # If adding this file would exceed limit, flush current chunk
            # (unless it's the first file in the chunk — always include at least 1)
            if current_files and current_size + fsize > max_size:
                zp = str(TEMP_DIR / f"{job_id}_batch_{chunk_idx}.zip")
                with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
                    for src, arc in current_files:
                        zf.write(src, arc)
                result_paths.append(zp)
                chunk_idx += 1
                current_files = []
                current_size = 0

            current_files.append((p, name))
            current_size += fsize

        # Flush remaining
        if current_files:
            zp = str(TEMP_DIR / f"{job_id}_batch_{chunk_idx}.zip")
            with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as zf:
                for src, arc in current_files:
                    zf.write(src, arc)
            result_paths.append(zp)

        return result_paths

    return await loop.run_in_executor(None, _zip)


def _make_bar(pct: float, width: int = 20) -> str:
    filled = int(pct * width)
    return "█" * filled + "░" * (width - filled)


def _stage_label(pct: float, msg: str, lang: str = "en") -> str:
    """Human-readable stage description based on progress."""
    if msg:
        return f"<i>{msg}</i>"
    if pct < 0.05:
        return _t("stage_analyse", lang)
    elif pct < 0.10:
        return _t("stage_plan", lang)
    elif pct < 0.80:
        return _t("stage_process", lang)
    elif pct < 0.95:
        return _t("stage_final", lang)
    else:
        return _t("stage_done", lang)


async def _cleanup_job(jobs: dict, user_jobs: dict, job_id: str, user_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    jobs.pop(job_id, None)
    job_list = user_jobs.get(user_id, [])
    if job_id in job_list:
        job_list.remove(job_id)
    if not job_list:
        user_jobs.pop(user_id, None)


def _safe_remove(path: Optional[str]) -> None:
    if path:
        try:
            os.remove(path)
        except OSError:
            pass


async def _cleanup_temp_dir(max_age_sec: int = 1800) -> None:
    """Remove temp files older than max_age_sec (default 30 min)."""
    now = time.time()
    removed = 0
    freed = 0
    for entry in os.scandir(str(TEMP_DIR)):
        if not entry.is_file():
            continue
        try:
            age = now - entry.stat().st_mtime
            if age > max_age_sec:
                size = entry.stat().st_size
                os.remove(entry.path)
                removed += 1
                freed += size
        except OSError:
            pass
    if removed:
        logger.info(f"Temp cleanup: removed {removed} files, freed {freed / 1024 / 1024:.1f} MB")


# ── Global singleton ───────────────────────────────────────────────────────────
queue = VideoQueue()
