from __future__ import annotations

import logging
from .config import settings
from .db import init_db
from .queue import procrastinate_app

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("clipfarm_worker")


def main() -> None:
    logger.info("Démarrage du worker ClipFarm (queue=gpu, concurrency=1)...")
    init_db()

    if settings.database_url.startswith("postgresql"):
        try:
            logger.info("Application du schéma Procrastinate sur Postgres...")
            with procrastinate_app.open():
                procrastinate_app.schema_manager.apply_schema()
            logger.info("Schéma Procrastinate prêt.")
        except Exception as exc:
            logger.warning("Impossible d'appliquer le schéma automatiquement: %s", exc)

        # Nettoyage des jobs orphelins bloqués en 'doing' par un arrêt inopiné
        try:
            from sqlmodel import Session, text
            from .db import engine
            with Session(engine) as s:
                stale = s.exec(text("UPDATE procrastinate_jobs SET status = 'failed' WHERE status = 'doing' RETURNING id")).all()
                if stale:
                    logger.warning("Réinitialisation de %d job(s) Procrastinate orphelins (marqués failed pour débloquer la file).", len(stale))
                # Récupérer les clips bloqués en 'rendering'
                s.exec(text("UPDATE clips SET status = 'ready' WHERE status = 'rendering' AND file_path IS NOT NULL"))
                s.exec(text("UPDATE clips SET status = 'failed' WHERE status = 'rendering' AND file_path IS NULL"))
                s.commit()
        except Exception as cln_err:
            logger.warning("Nettoyage des jobs orphelins ignoré: %s", cln_err)

    logger.info("Worker prêt à recevoir les jobs GPU et Publication.")
    procrastinate_app.run_worker(queues=["gpu", "publish"], concurrency=1)


if __name__ == "__main__":
    main()
