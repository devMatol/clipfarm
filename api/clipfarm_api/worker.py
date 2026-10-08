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

    logger.info("Worker prêt à recevoir les jobs GPU et Publication.")
    procrastinate_app.run_worker(queues=["gpu", "publish"], concurrency=1)


if __name__ == "__main__":
    main()
