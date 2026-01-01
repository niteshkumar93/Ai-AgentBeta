import json
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import Baseline

# Optional GitHub backup
try:
    from github_storage import GitHubStorage
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False


class BaselineService:
    # --------------------------------------------------
    # SYNC BASELINES FROM GITHUB → SQLITE
    # --------------------------------------------------
    def sync_from_github(self) -> int:
        """
        Pull baselines from GitHub and store them in SQLite
        so other machines can see the same baselines.
        """
        if not self.github:
            return 0

        imported = 0
        baselines = self.github.list_baselines(folder="baselines_backup/sqlite")

        for b in baselines:
            content = self.github.load_baseline(
                b["name"],
                folder="baselines_backup/sqlite"
            )
            if not content:
                continue

            try:
                data = json.loads(content)

                # Filename format:
                # project_platform_id.json
                name = b["name"].replace(".json", "")
                parts = name.split("_", 2)

                if len(parts) < 2:
                    continue

                project = parts[0]
                platform = parts[1]

                self.save(
                    project=project,
                    platform=platform,
                    failures=data,
                    label="Synced from GitHub"
                )
                imported += 1

            except Exception as e:
                print(f"Sync failed for {b['name']}: {e}")
                continue

        return imported

    def __init__(self, github_storage: GitHubStorage | None = None):
        self.github = github_storage

    def _db(self) -> Session:
        return SessionLocal()

    # ----------------------------
    # SAVE
    # ----------------------------
    def save(
        self,
        project: str,
        platform: str,
        failures: List[Dict],
        label: Optional[str] = None
    ) -> int:
        db = self._db()
        try:
            baseline = Baseline(
                project=project,
                platform=platform,
                label=label,
                data=json.dumps(failures)
            )
            db.add(baseline)
            db.commit()
            db.refresh(baseline)

            # GitHub backup (NON-BLOCKING)
            if self.github:
                self._backup_to_github(project, platform, baseline.id, failures)

            return baseline.id
        finally:
            db.close()

    # ----------------------------
    # LOAD LATEST
    # ----------------------------
    def get_latest(self, project: str, platform: str) -> Optional[List[Dict]]:
        db = self._db()
        try:
            baseline = (
                db.query(Baseline)
                .filter_by(project=project, platform=platform)
                .order_by(Baseline.created_at.desc())
                .first()
            )
            return json.loads(baseline.data) if baseline else None
        finally:
            db.close()

    # ----------------------------
    # LIST
    # ----------------------------
    def list(self, project: str, platform: str):
        db = self._db()
        try:
            return (
                db.query(Baseline)
                .filter_by(project=project, platform=platform)
                .order_by(Baseline.created_at.desc())
                .all()
            )
        finally:
            db.close()

    # ----------------------------
    # BACKUP
    # ----------------------------
    def _backup_to_github(self, project, platform, baseline_id, data):
        try:
            filename = f"{project}_{platform}_{baseline_id}.json"
            self.github.save_baseline(
                json.dumps(data, indent=2),
                filename,
                folder="baselines_backup/sqlite"
            )
        except Exception as e:
            print(f"GitHub backup failed (ignored): {e}")
