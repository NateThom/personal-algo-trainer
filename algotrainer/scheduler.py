from datetime import datetime

from fsrs import Card, Rating, Scheduler

RATING_BY_NAME: dict[str, int] = {"again": 1, "hard": 2, "good": 3, "easy": 4}


class SrsScheduler:
    def __init__(self) -> None:
        # Deterministic scheduling (no fuzz) so tests and intervals are reproducible.
        self._scheduler = Scheduler(enable_fuzzing=False)

    def review(
        self, card_json: str | None, rating: int, when: datetime
    ) -> tuple[str, datetime, str]:
        card = Card.from_json(card_json) if card_json else Card()
        card, review_log = self._scheduler.review_card(
            card=card, rating=Rating(rating), review_datetime=when
        )
        return card.to_json(), card.due, review_log.to_json()

    def due_problem_ids(
        self, due_map: dict[str, datetime], all_ids: list[str], now: datetime
    ) -> list[str]:
        out = []
        for pid in all_ids:
            due = due_map.get(pid)
            if due is None or due <= now:
                out.append(pid)
        return out
