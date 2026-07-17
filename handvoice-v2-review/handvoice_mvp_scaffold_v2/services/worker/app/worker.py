"""No asynchronous worker is used in the competition MVP.

The previous infinite sleep loop implied that queue processing existed. Measurement
analysis now runs synchronously through POST /v1/task-instances/{id}/measure.
Keep this module only to fail loudly if an old command still invokes it.
"""


def main() -> None:
    raise SystemExit(
        "The competition MVP has no background worker. Use the synchronous measurement API."
    )


if __name__ == "__main__":
    main()
