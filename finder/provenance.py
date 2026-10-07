"""Conservative field provenance; never create or modify aviation values."""
import math

def duration_provenance(row: dict) -> str:
    """The supplied importer nulls durations with fewer than 3 complete tracks.

    Such non-null values in the supplied database were filled after import.
    Their original transformation is not documented, so do not call them
    observed airborne medians or interpret their bounds as percentiles.
    """
    if row.get('duration_min') is None:
        return 'UNKNOWN'
    complete = row.get('n_complete')
    if isinstance(complete, (int, float)) and complete >= 3:
        return 'AGGREGATED_COMPLETE_TRACKS'
    distance, duration = row.get('distance_nm'), row.get('duration_min')
    if (isinstance(distance, (int, float)) and math.isfinite(distance) and distance >= 0
            and isinstance(duration, (int, float)) and math.isfinite(duration)
            and round(distance / 390 * 60 + 15) == duration):
        # Numerical compatibility does not identify the original script/author.
        return 'ESTIMATED_DISTANCE_HEURISTIC'
    return 'POST_IMPORT_UNVERIFIED'
