"""User preferences: course/deadline colors and exam states."""

from __future__ import annotations

from dataclasses import dataclass, field

from unical.events import ExamOccurrence, exam_key, title_from_exam_key
from unical.palette import GoogleColor


@dataclass(frozen=True)
class ExamPreference:
    color: GoogleColor
    subscribed: bool


@dataclass
class Preferences:
    """In-memory user preferences. Insertion order is preserved on save."""

    course_colors: dict[str, GoogleColor] = field(default_factory=dict)
    exams: dict[str, ExamPreference] = field(default_factory=dict)
    deadline_colors: dict[str, GoogleColor] = field(default_factory=dict)

    def course_color(self, course: str) -> GoogleColor | None:
        return self.course_colors.get(course)

    def set_course_color(self, course: str, color: GoogleColor) -> None:
        self.course_colors[course] = color

    def deadline_color(self, deadline: str) -> GoogleColor | None:
        return self.deadline_colors.get(deadline)

    def set_deadline_color(self, deadline: str, color: GoogleColor) -> None:
        self.deadline_colors[deadline] = color

    def exam(self, occurrence: ExamOccurrence) -> ExamPreference | None:
        pref = self.exams.get(occurrence.key)
        if pref is not None:
            return pref
        if " " in occurrence.date:
            base_date = occurrence.date.split(" ")[0]
            base_key = exam_key(occurrence.title, base_date)
            return self.exams.get(base_key)
        return None

    def set_exam(self, occurrence: ExamOccurrence, preference: ExamPreference) -> None:
        self.exams[occurrence.key] = preference

    def subscribed_exam_titles(self) -> set[str]:
        """Titles of exams the user is subscribed to on at least one date."""
        return {
            title_from_exam_key(key)
            for key, preference in self.exams.items()
            if preference.subscribed
        }
