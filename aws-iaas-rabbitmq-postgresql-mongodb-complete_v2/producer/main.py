import time

from config import config
from scenarios import run_order_lifecycle


def main():
    while True:
        try:
            run_order_lifecycle()
        except Exception as exc:
            print(f"Synthetic producer cycle failed: {exc}", flush=True)
        time.sleep(config.cycle_interval_seconds)


if __name__ == "__main__":
    main()
