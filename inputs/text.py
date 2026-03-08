from typing import List


def get_text_query(argv: List[str]) -> str:
    if argv:
        return " ".join(argv).strip()
    return input("Enter song name: ").strip()

