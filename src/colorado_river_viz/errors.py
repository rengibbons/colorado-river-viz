"""Exception types raised by the data pipeline."""


class ColoradoRiverVizError(Exception):
    """Base class for errors raised by this package."""


class CacheMissError(ColoradoRiverVizError):
    """A series was requested offline but isn't in the local cache."""


class SourceUnavailableError(ColoradoRiverVizError):
    """A remote data source kept failing after every retry."""


class IncompleteWaterYearError(ColoradoRiverVizError):
    """A water year has too few days of data for the requested metric."""


class UnexpectedSourceFormatError(ColoradoRiverVizError):
    """A downloaded file or API response doesn't have the expected structure."""
