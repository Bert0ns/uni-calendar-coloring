"""Coloring strategies: pure lookups from an event to a color.

Strategies never prompt nor perform I/O; they only read :class:`Preferences`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from unical.events import Event, ExamOccurrence, exam_key, start_time
from unical.palette import GoogleColor
from unical.preferences import Preferences
from unical.rules import Classifier
from unical.suggestions import suggest_color
from unical.targets import SyncTarget


class EventColoringStrategy(ABC):
    @abstractmethod
    def determine_color(self, event: Event) -> GoogleColor | None:
        """Returns the color for the event, or ``None`` if it does not apply."""


class CompositeColoringStrategy(EventColoringStrategy):
    """Returns the color of the first strategy that matches."""

    def __init__(self, strategies: Sequence[EventColoringStrategy]) -> None:
        self.strategies = list(strategies)

    def determine_color(self, event: Event) -> GoogleColor | None:
        for strategy in self.strategies:
            color = strategy.determine_color(event)
            if color is not None:
                return color
        return None


class LectureColoringStrategy(EventColoringStrategy):
    """Colors lectures with their course color (or its deterministic suggestion)."""

    def __init__(self, preferences: Preferences, classifier: Classifier) -> None:
        self.preferences = preferences
        self.classifier = classifier

    def determine_color(self, event: Event) -> GoogleColor | None:
        course = self.classifier.course_name(event)
        if course is None:
            return None
        return self.preferences.course_color(course) or suggest_color(course)


class ExamColoringStrategy(EventColoringStrategy):
    """Colors exam sessions with their saved color (``None`` if unknown)."""

    def __init__(self, preferences: Preferences, classifier: Classifier) -> None:
        self.preferences = preferences
        self.classifier = classifier
        self._counts: dict[tuple[str, str], int] = {}

    def determine_color(self, event: Event) -> GoogleColor | None:
        occurrence = self.classifier.exam_occurrence(event)
        if occurrence is None:
            return None
        # 1. Direct match with occurrence key
        preference = self.preferences.exam(occurrence)
        if preference is not None:
            return preference.color

        # 2. Match with timed key if event has a start time
        time = start_time(event)
        if time:
            timed_occ = ExamOccurrence(
                occurrence.title, f"{occurrence.date} {time}", occurrence.enrollment
            )
            timed_pref = self.preferences.exam(timed_occ)
            if timed_pref is not None:
                return timed_pref.color

        # 3. Match with indexed key if disambiguated by index
        pair = (occurrence.title, occurrence.date)
        idx = self._counts.get(pair, 0) + 1
        self._counts[pair] = idx
        suffix = f" {time} #{idx}" if time else f" #{idx}"
        indexed_key = exam_key(occurrence.title, f"{occurrence.date}{suffix}")
        if indexed_key in self.preferences.exams:
            return self.preferences.exams[indexed_key].color

        return None


class DeadlineColoringStrategy(EventColoringStrategy):
    """Colors deadlines with their saved color (or its deterministic suggestion)."""

    def __init__(self, preferences: Preferences, classifier: Classifier) -> None:
        self.preferences = preferences
        self.classifier = classifier

    def determine_color(self, event: Event) -> GoogleColor | None:
        deadline = self.classifier.deadline_name(event)
        if deadline is None:
            return None
        return self.preferences.deadline_color(deadline) or suggest_color(deadline)


def strategy_for(
    target: SyncTarget, preferences: Preferences, classifier: Classifier
) -> EventColoringStrategy:
    strategies: list[EventColoringStrategy] = []
    if target.includes_exams:
        strategies.append(ExamColoringStrategy(preferences, classifier))
    if target.includes_lectures:
        strategies.append(LectureColoringStrategy(preferences, classifier))
    if target.includes_deadlines:
        strategies.append(DeadlineColoringStrategy(preferences, classifier))
    return CompositeColoringStrategy(strategies)
