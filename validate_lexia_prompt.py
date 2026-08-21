import argparse
from pathlib import Path

from prompt.validator import PromptValidator


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Valida un expediente .lexia según "
            "LexIA Prompt Protocol 2.0."
        )
    )
    parser.add_argument(
        "path",
        type=Path,
    )
    args = parser.parse_args()

    content = args.path.read_text(
        encoding="utf-8"
    )
    result = PromptValidator().validate(
        content
    )

    print(
        "VÁLIDO"
        if result.valid
        else "INVÁLIDO"
    )

    for issue in result.issues:
        print(
            f"[{issue.severity.upper()}] "
            f"{issue.code}: {issue.message}"
        )

    raise SystemExit(
        0 if result.valid else 1
    )


if __name__ == "__main__":
    main()
