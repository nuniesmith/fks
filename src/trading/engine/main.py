"""Public entrypoint for engine service (flattened layout)."""

from _impl import main as _impl_main  # type: ignore
from _impl import start_engine, start_template_service


def main():  # thin wrapper to keep stable signature
    return _impl_main()


__all__ = ["main", "start_engine", "start_template_service"]

if __name__ == "__main__":  # allow direct script execution inside container
    main()
