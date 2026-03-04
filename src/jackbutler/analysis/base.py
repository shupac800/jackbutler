from abc import ABC, abstractmethod

from jackbutler.parsing.models import ParsedMeasure


class BaseAnalyzer(ABC):
    """Base class for all measure-level analyzers."""

    @abstractmethod
    def analyze_measure(self, measure: ParsedMeasure, context: dict) -> dict:
        """Analyze a single measure and return findings.

        Args:
            measure: The parsed measure to analyze.
            context: Shared context dict. Upstream analyzers write results here
                     so downstream analyzers can use them (e.g. detected key).

        Returns:
            A dict of findings to merge into the measure analysis.
        """
        ...
