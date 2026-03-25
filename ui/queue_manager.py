import logging
import threading
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from playlistmigrator import auth as auth_module
from playlistmigrator import backend

# Job statuses
STATUS_PENDING   = "pending"
STATUS_RUNNING   = "running"
STATUS_DONE      = "done"
STATUS_ERROR     = "error"
STATUS_SKIPPED   = "skipped"

# A single job in the queue
@dataclass
class TransferJob:
    job_id: str                  # uuid4
    src_playlist_id: str         # ID from playlists.json (the CSV filename)
    src_playlist_name: str       # Human-readable name, looked up at submission time
    dst_playlist_id: Optional[str]  # YTMusic playlist ID; None = auto-create
    dst_playlist_name: Optional[str]
    algo: int                    # 0=exact, 1=extended, 2=approximate
    dry_run: bool
    track_sleep: float
    privacy: str                 # PRIVATE / PUBLIC / UNLISTED
    status: str                  # one of STATUS_* constants above
    progress: int                # 0-100 integer percent
    total_tracks: int            # set when job starts
    tracks_done: int             # incremented as tracks complete
    tracks_added: int            # successful adds
    tracks_errored: int          # failed lookups
    tracks_skipped: int          # duplicates
    log_lines: List[str]         # live log messages, capped at last 200 lines
    submitted_at: str            # ISO timestamp
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None # set if status == ERROR

class _JobLogHandler(logging.Handler):
    """Routes backend log records into a TransferJob's log_lines list."""

    def __init__(self, job: "TransferJob"):
        super().__init__()
        self.job = job

    def emit(self, record):
        msg = self.format(record)
        self.job.log_lines.append(msg)
        if len(self.job.log_lines) > 200:
            self.job.log_lines.pop(0)

class QueueManager:
    """
    Singleton stored in st.session_state["queue_manager"].
    Manages a list of TransferJob objects and a background worker thread.
    """

    def __init__(self):
        self.jobs: List[TransferJob] = []
        self._lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None

    def submit(self, job: TransferJob) -> None:
        """Add a job to the queue and start worker if not running."""
        with self._lock:
            self.jobs.append(job)
        self._ensure_worker_running()

    def _ensure_worker_running(self) -> None:
        """Start worker thread if it's not alive."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._worker_thread = threading.Thread(target=self._run_worker, daemon=True)
            self._worker_thread.start()

    def _run_worker(self) -> None:
        """
        Worker loop: picks the next pending job, runs it, then loops.
        Runs in a background daemon thread - survives page navigation.
        """
        while True:
            job = self._next_pending_job()
            if job is None:
                break  # No more pending jobs; thread exits (will restart on next submit)
            self._execute_job(job)

    def _next_pending_job(self) -> Optional[TransferJob]:
        with self._lock:
            for job in self.jobs:
                if job.status == STATUS_PENDING:
                    return job
        return None

    def _execute_job(self, job: TransferJob) -> None:
        """
        Runs backend.copier() with a logging handler that routes log records
        into the job's live log, and reads structured results from the return value.
        """
        job.status = STATUS_RUNNING
        job.started_at = datetime.utcnow().isoformat()

        handler = _JobLogHandler(job)
        handler.setFormatter(logging.Formatter("%(levelname)s — %(message)s"))
        backend_logger = logging.getLogger("playlistmigrator.backend")
        backend_logger.addHandler(handler)
        backend_logger.setLevel(logging.DEBUG)

        try:
            yt = auth_module.get_ytmusic()

            spotify_pls = backend.load_playlists_json()
            for pl in spotify_pls["playlists"]:
                if pl["id"] == job.src_playlist_id:
                    job.total_tracks = len(pl["tracks"])
                    break

            def tracked_iter():
                for song in backend.iter_spotify_playlist(job.src_playlist_id):
                    job.tracks_done += 1
                    job.progress = int((job.tracks_done / max(job.total_tracks, 1)) * 100)
                    yield song

            dst_id = job.dst_playlist_id
            if dst_id is None:
                dst_id = backend._ytmusic_create_playlist(
                    yt,
                    title=job.src_playlist_name,
                    description="Imported from CSV",
                    privacy_status=job.privacy
                )
                job.dst_playlist_id = dst_id

            results = backend.copier(
                tracked_iter(),
                dst_pl_id=dst_id,
                dry_run=job.dry_run,
                track_sleep=job.track_sleep,
                yt_search_algo=job.algo,
                yt=yt,
                csv_file_id=job.src_playlist_id,
                playlist_name=job.src_playlist_name,
            )

            if results:
                job.tracks_added = results.get("added", 0)
                job.tracks_errored = results.get("errors", 0)
                job.tracks_skipped = results.get("duplicates", 0)

            job.status = STATUS_DONE
            job.progress = 100

        except Exception as e:
            job.status = STATUS_ERROR
            job.error_message = str(e)

        finally:
            backend_logger.removeHandler(handler)
            job.finished_at = datetime.utcnow().isoformat()

    def get_jobs(self) -> List[TransferJob]:
        with self._lock:
            return list(self.jobs)

    def cancel_pending(self, job_id: str) -> None:
        """Remove a job from the queue if it hasn't started yet."""
        with self._lock:
            self.jobs = [j for j in self.jobs if not (j.job_id == job_id and j.status == STATUS_PENDING)]

    def clear_finished(self) -> None:
        """Remove all done/error/skipped jobs from the list."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status in (STATUS_PENDING, STATUS_RUNNING)]

    @property
    def is_busy(self) -> bool:
        return any(j.status == STATUS_RUNNING for j in self.jobs)

    @property
    def pending_count(self) -> int:
        return sum(1 for j in self.jobs if j.status == STATUS_PENDING)
