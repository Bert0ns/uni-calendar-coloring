"""Discovery of the courses and exams contained in the source calendar."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from unical.events import Event, ExamOccurrence, start_date, start_time
from unical.rules import Classification, Classifier, EventKind


@dataclass(frozen=True)
class Catalog:
    """Courses, exams and deadlines found in the source calendar, in event order."""

    courses: tuple[str, ...] = ()
    exam_occurrences: tuple[ExamOccurrence, ...] = ()
    """Every exam event, in order, duplicates included."""
    deadlines: tuple[str, ...] = ()

    @property
    def exams(self) -> tuple[ExamOccurrence, ...]:
        """Distinct exam sessions (first occurrence wins)."""
        seen: set[str] = set()
        unique: list[ExamOccurrence] = []
        for occurrence in self.exam_occurrences:
            if occurrence.key not in seen:
                seen.add(occurrence.key)
                unique.append(occurrence)
        return tuple(unique)


def discover(events: Iterable[Event], classifier: Classifier) -> Catalog:
    """Lists what the events contain, as classified by the profile's rules."""
    courses: dict[str, None] = {}
    deadlines: dict[str, None] = {}
    raw_exams: list[tuple[Event, Classification]] = []

    for event in events:
        classification = classifier.classify(event)
        if classification is None:
            continue
        if classification.kind is EventKind.EXAM:
            raw_exams.append((event, classification))
        elif classification.kind is EventKind.LECTURE:
            courses.setdefault(classification.name, None)
        else:
            deadlines.setdefault(classification.name, None)

    times_by_group: dict[tuple[str, str], set[str]] = {}
    for event, classification in raw_exams:
        t = start_time(event)
        if t is not None:
            group_key = (classification.name, start_date(event))
            times_by_group.setdefault(group_key, set()).add(t)

    exams: list[ExamOccurrence] = []
    for event, classification in raw_exams:
        d_str = start_date(event)
        group_key = (classification.name, d_str)
        distinct_times = times_by_group.get(group_key, set())
        t = start_time(event)
        date_label = f"{d_str} {t}" if len(distinct_times) > 1 and t is not None else d_str
        exams.append(
            ExamOccurrence(
                title=classification.name,
                date=date_label,
                enrollment=classifier.enrollment(event),
            )
        )

    return Catalog(
        courses=tuple(courses),
        exam_occurrences=tuple(exams),
        deadlines=tuple(deadlines),
    )
