import asyncio

from vector_match.core.config import get_settings
from vector_match.worker.runner import run


def main() -> None:
    asyncio.run(run(get_settings()))


if __name__ == "__main__":
    main()
