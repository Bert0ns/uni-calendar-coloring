"""Discovery of the courses and exams contained in the source calendar."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from unical.events import (
    Event,
    ExamOccurrence,
    description_of,
    start_date,
    start_time,
    summary_of,
)
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
    seen_event_sig: set[tuple[object, ...]] = set()

    for event in events:
        classification = classifier.classify(event)
        if classification is None:
            continue
        if classification.kind is EventKind.EXAM:
            sig = (
                event.get("id"),
                summary_of(event),
                description_of(event),
                str(event.get("start")),
                str(event.get("end")),
            )
            if sig in seen_event_sig:
                continue
            seen_event_sig.add(sig)
            raw_exams.append((event, classification))
        elif classification.kind is EventKind.LECTURE:
            courses.setdefault(classification.name, None)
        else:
            deadlines.setdefault(classification.name, None)

    events_by_group: dict[tuple[str, str], list[Event]] = {}
    for event, classification in raw_exams:
        group_key = (classification.name, start_date(event))
        events_by_group.setdefault(group_key, []).append(event)

    date_labels: dict[int, str] = {}
    for (_name, d_str), group in events_by_group.items():
        if len(group) == 1:
            date_labels[id(group[0])] = d_str
        else:
            times = [start_time(ev) for ev in group]
            if all(t is not None for t in times) and len(set(times)) == len(times):
                for ev in group:
                    date_labels[id(ev)] = f"{d_str} {start_time(ev)}"
            else:
                for idx, ev in enumerate(group, start=1):
                    t = start_time(ev)
                    if t is not None:
                        date_labels[id(ev)] = f"{d_str} {t} #{idx}"
                    else:
                        date_labels[id(ev)] = f"{d_str} #{idx}"

    exams: list[ExamOccurrence] = [
        ExamOccurrence(
            title=classification.name,
            date=date_labels[id(event)],
            enrollment=classifier.enrollment(event),
        )
        for event, classification in raw_exams
    ]

    return Catalog(
        courses=tuple(courses),
        exam_occurrences=tuple(exams),
        deadlines=tuple(deadlines),
    )
