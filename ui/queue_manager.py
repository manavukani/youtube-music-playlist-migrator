import sys
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
        Runs backend.copy_playlist() with a patched copier that reports
        progress back to the job object in real time.
        """
        job.status = STATUS_RUNNING
        job.started_at = datetime.utcnow().isoformat()

        try:
            yt = auth_module.get_ytmusic()

            # Pre-count total tracks for progress bar
            spotify_pls = backend.load_playlists_json()
            for pl in spotify_pls["playlists"]:
                if pl["id"] == job.src_playlist_id:
                    job.total_tracks = len(pl["tracks"])
                    break

            # Build a progress-tracking iterator wrapper
            def tracked_iter():
                for song in backend.iter_spotify_playlist(job.src_playlist_id):
                    job.tracks_done += 1
                    job.progress = int((job.tracks_done / max(job.total_tracks, 1)) * 100)
                    yield song

            # Capture stdout into log_lines
            class LogCapture:
                def write(self_inner, msg):
                    if msg.strip():
                        job.log_lines.append(msg.strip())

                        # Custom parsing to capture counts from logs
                        lower_msg = msg.strip().lower()
                        if "error:" in lower_msg and "unable to look up song" in lower_msg:
                            job.tracks_errored += 1
                        elif "(duplicate" in lower_msg:
                            job.tracks_skipped += 1

                        # Final summary logic could also go here, but since the copier prints
                        # a summary at the end, we'll try to parse that.
                        if msg.startswith("Added "):
                            try:
                                parts = msg.strip().split()
                                # Added 1 tracks, encountered 0 duplicates, 0 errors
                                if len(parts) >= 2:
                                    job.tracks_added = int(parts[1])
                            except:
                                pass

                        if len(job.log_lines) > 200:
                            job.log_lines.pop(0)
                def flush(self_inner): pass

            old_stdout = sys.stdout
            sys.stdout = LogCapture()

            try:
                # Resolve dst playlist ID (create if needed)
                dst_id = job.dst_playlist_id
                if dst_id is None:
                    dst_id = backend._ytmusic_create_playlist(
                        yt,
                        title=job.src_playlist_name,
                        description="Imported from CSV",
                        privacy_status=job.privacy
                    )
                    job.dst_playlist_id = dst_id

                backend.copier(
                    tracked_iter(),
                    dst_pl_id=dst_id,
                    dry_run=job.dry_run,
                    track_sleep=job.track_sleep,
                    yt_search_algo=job.algo,
                    yt=yt,
                    csv_file_id=job.src_playlist_id,
                    playlist_name=job.src_playlist_name,
                )
            finally:
                sys.stdout = old_stdout

            job.status = STATUS_DONE
            job.progress = 100

        except Exception as e:
            job.status = STATUS_ERROR
            job.error_message = str(e)

        finally:
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
