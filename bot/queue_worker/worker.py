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

from bot.config import MAX_CONCURRENT_JOBS, RATE_LIMIT_PER_MIN, TEMP_DIR

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
        self._user_job:  dict[int, str]     = {}  # user_id → active job_id
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

    def user_has_active_job(self, user_id: int) -> bool:
        job_id = self._user_job.get(user_id)
        if not job_id:
            return False
        job = self._jobs.get(job_id)
        if job is None:
            return False
        if job.status not in (JobStatus.PENDING, JobStatus.PROCESSING):
            return False
        # Auto-expire stuck jobs (>10 min for processing, >5 min for pending)
        age = time.time() - job.created_at
        if job.status == JobStatus.PROCESSING and age > 600:
            logger.warning(f"Force-expiring stuck PROCESSING job {job.id} (age={age:.0f}s)")
            job.status = JobStatus.FAILED
            job.error = "Timeout: job took too long"
            return False
        if job.status == JobStatus.PENDING and age > 300:
            logger.warning(f"Force-expiring stuck PENDING job {job.id} (age={age:.0f}s)")
            job.status = JobStatus.FAILED
            job.error = "Timeout: job stuck in queue"
            return False
        return True

    def get_user_job(self, user_id: int) -> Optional[Job]:
        job_id = self._user_job.get(user_id)
        return self._jobs.get(job_id) if job_id else None

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
        self._user_job[user_id] = job.id
        await self._queue.put(job)
        logger.info(f"Enqueued job {job.id} for user {user_id}")
        return job

    def cancel_user_job(self, user_id: int) -> bool:
        job = self.get_user_job(user_id)
        if job and job.status == JobStatus.PENDING:
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
        variation = job.variation  # ±% разброс интенсивности

        # Telegram bot API limit for sending files
        TG_MAX_FILE_SIZE = 49 * 1024 * 1024  # 49 MB (safe margin under 50MB)

        # Строки прогресса для каждой копии
        copy_status = ["⬜ ожидает"] * copies
        _last_update = [0.0]  # троттлинг — не чаще раза в 3 секунды

        async def update_progress_msg(copy_idx: int, pct: float, msg: str = "") -> None:
            """Обновляет общее сообщение прогресса (не чаще 1 раза в 3с)."""
            if not self._bot or not job.message_id:
                return
            now = time.time()
            # Обновляем только раз в 3 секунды, кроме финального (pct==1.0)
            if pct < 1.0 and now - _last_update[0] < 3.0:
                copy_status[copy_idx] = f"{_make_bar(pct)} {int(pct*100)}%"
                return
            _last_update[0] = now
            try:
                bar = _make_bar(pct)
                copy_status[copy_idx] = f"{bar} {int(pct*100)}%  {_stage_label(pct, msg)}"

                lines = [f"⚙️ <b>Обрабатываю {copies} {'копию' if copies==1 else 'копии' if copies<=4 else 'копий'}…</b>\n"]
                for i, st in enumerate(copy_status):
                    prefix = "▶️" if i == copy_idx else ("✅" if "100%" in st else "⬜")
                    lines.append(f"{prefix} Копия {i+1}/{copies}:  {st}")

                await self._bot.edit_message_text(
                    text="\n".join(lines),
                    chat_id=job.chat_id,
                    message_id=job.message_id,
                    parse_mode="HTML",
                )
            except Exception:
                pass

        completed_paths: list[str] = []
        all_hashes_unique = True
        seen_hashes: set[str] = set()
        send_failed = False  # track if any send to user failed

        try:
            for i in range(copies):
                copy_status[i] = "⚙️ запускается…"

                # Разброс интенсивности: клонируем настройки и случайно меняем intensity
                import copy as _copy
                import random
                cur_settings = _copy.deepcopy(job.settings)

                if variation > 0 and copies > 1:
                    rng = random.Random(i * 0xABCD1234)
                    for ms in cur_settings.methods.values():
                        if not ms.enabled:
                            continue
                        # variation is ±% (e.g. 10 → ±10% of current intensity)
                        delta = rng.uniform(-variation, variation)
                        new_intensity = ms.intensity + delta
                        ms.intensity = max(1, min(100, round(new_intensity)))

                # Уникальный seed для каждой копии
                job_seed = random.randint(0, 2**32 - 1)

                async def progress_cb(pct: float, msg: str = "", _i=i) -> None:
                    await update_progress_msg(_i, pct, msg)

                result = await process_video(
                    input_path=job.input_path,
                    user_settings=cur_settings,
                    progress_cb=progress_cb,
                    job_seed=job_seed,
                )

                # Validate output is not empty
                out_size = result.get("output_size", 0)
                if out_size < 1024:
                    logger.error(f"Job {job.id} copy {i+1}: output too small ({out_size} bytes), skipping")
                    _safe_remove(result["output_path"])
                    copy_status[i] = "⚠️ пустой файл"
                    continue

                out_hash = result["output_hash_md5"]
                if out_hash in seen_hashes:
                    all_hashes_unique = False
                seen_hashes.add(out_hash)

                copy_status[i] = f"✅ готово  <code>{out_hash[:8]}…</code>"
                completed_paths.append(result["output_path"])
                await update_progress_msg(i, 1.0, "Готово!")

                # Отправляем сразу если копий мало (≤4)
                if copies <= 4 and self._bot:
                    report = build_report(result)
                    caption = (
                        f"📦 <b>Копия {i+1}/{copies}</b>\n"
                        f"{'✅ Хеш уникален' if result['input_hash_md5'] != out_hash else '⚠️ Хеш совпал'}\n\n"
                        + report
                    ) if copies > 1 else report
                    try:
                        from aiogram.types import FSInputFile
                        if out_size > TG_MAX_FILE_SIZE:
                            await self._bot.send_message(
                                chat_id=job.chat_id,
                                text=f"⚠️ Копия {i+1} слишком большая ({out_size/1024/1024:.0f} МБ > 50 МБ лимит Telegram).\n"
                                     f"Файл обработан, но не может быть отправлен.",
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

            job.status = JobStatus.DONE

            # Для 5+ копий — отправляем порциями (zip'ы до 49MB)
            if copies >= 5 and self._bot and completed_paths:
                await self._bot.edit_message_text(
                    text=f"📦 <b>Отправляю {len(completed_paths)} файлов…</b>",
                    chat_id=job.chat_id,
                    message_id=job.message_id,
                    parse_mode="HTML",
                )
                hash_note = "✅ Все хеши уникальны" if all_hashes_unique else "⚠️ Часть хешей совпала"
                var_note = f"±{variation}%" if variation > 0 else "выкл"

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
                        part_label = f" (часть {zi+1}/{len(zip_paths)})" if len(zip_paths) > 1 else ""
                        doc = FSInputFile(path=zp, filename=f"uniqueluzer_{len(completed_paths)}copies{part_label}.zip")
                        await self._bot.send_document(
                            chat_id=job.chat_id,
                            document=doc,
                            caption=(
                                f"✅ <b>Готово! {len(completed_paths)} копий</b>{part_label}\n"
                                f"{hash_note}\n"
                                f"Разброс параметров: {var_note}"
                            ),
                            parse_mode="HTML",
                        )
                        sent_count += 1
                    except Exception as e:
                        logger.error(f"Failed to send zip chunk {zi+1}: {e}")
                        send_failed = True
                    finally:
                        _safe_remove(zp)

                if sent_count == 0 and completed_paths:
                    # All zips failed to send — try sending files individually
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
                                caption=f"📦 Копия {fi+1}/{len(completed_paths)}",
                                parse_mode="HTML",
                            )
                            send_failed = False  # at least some sent
                        except Exception:
                            pass

            # Обновляем/удаляем сообщение прогресса
            if self._bot:
                try:
                    if send_failed:
                        # Don't delete progress — show warning
                        await self._bot.edit_message_text(
                            text=(
                                f"⚠️ <b>Обработка завершена, но не все файлы удалось отправить</b>\n"
                                f"Обработано: {len(completed_paths)}/{copies}\n"
                                f"Проблема: файл(ы) превышают лимит Telegram (50 МБ) или ошибка сети.\n"
                                f"Попробуйте уменьшить количество копий."
                            ),
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
                        text=f"❌ <b>Ошибка обработки:</b>\n{e}",
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
                        text=f"❌ <b>Неожиданная ошибка:</b>\n{str(e)[:300]}",
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

            asyncio.create_task(_cleanup_job(self._jobs, job.id, delay=300))


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


def _stage_label(pct: float, msg: str) -> str:
    """Human-readable stage description based on progress."""
    if msg:
        return f"<i>{msg}</i>"
    if pct < 0.05:
        return "<i>🔍 Анализирую видео…</i>"
    elif pct < 0.10:
        return "<i>📋 Составляю план обработки…</i>"
    elif pct < 0.80:
        return "<i>⚙️ Применяю методы уникализации…</i>"
    elif pct < 0.95:
        return "<i>🔬 Финальная обработка…</i>"
    else:
        return "<i>✅ Завершаю…</i>"


async def _cleanup_job(jobs: dict, job_id: str, delay: int) -> None:
    await asyncio.sleep(delay)
    jobs.pop(job_id, None)


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
