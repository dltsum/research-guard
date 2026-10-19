"""Dependency-free audit errors shared across independently installed groups."""
from research_guard_core import GuardError

TEXT_SUFFIXES = {".tex", ".md", ".markdown", ".txt", ".rst", ".qmd"}


class LanguageError(ValueError):
    pass


class FigureError(ValueError):
    pass


class OpenReviewCalibrationError(ValueError):
    pass


class AIReviewerAuditError(ValueError):
    pass


class ConstructiveNumericalError(GuardError):
    pass
