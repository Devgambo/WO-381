"""RQ worker entrypoint.

Run alongside the API:

    python worker.py

or directly with the RQ CLI:

    rq worker compliance --url $REDIS_URL

The worker process is where the expensive imports actually land — torch, the
BGE embedder, the cross-encoder reranker, ChromaDB. Keep it on an instance with
enough RAM (see DEPLOYMENT.md; the local models need ~2 GB).
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("compliance.worker")


def main() -> None:
    from rq import Queue, SimpleWorker, Worker

    from jobs import JOB_QUEUE_NAME, get_redis

    connection = get_redis()
    queue = Queue(JOB_QUEUE_NAME, connection=connection)

    # SimpleWorker (no fork) is required on Windows and is fine on a single-core
    # free-tier container; the classic forking Worker is used elsewhere because
    # it isolates each job and frees the big ML allocations between runs.
    worker_cls = SimpleWorker if os.name == "nt" or os.getenv("RQ_SIMPLE_WORKER") == "1" else Worker
    log.info("Starting %s on queue '%s'", worker_cls.__name__, JOB_QUEUE_NAME)
    worker = worker_cls([queue], connection=connection)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
