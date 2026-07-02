"""The error taxonomy that codes why an attempt was less than perfect.
Drives remediation/scheduling in later plans; here it constrains verdicts."""

ERROR_CODES: tuple[str, ...] = (
    "pattern_misidentification",       # reached for the wrong schema
    "approach_correct_execution_bug",  # right idea, off-by-one / base case / boundary
    "complexity_suboptimal",           # worked but not optimal
    "incomplete_knowledge",            # missing a data structure / API
    "got_stuck_no_idea",               # no retrieval at all
    "careless_time_pressure",          # avoidable slip
)


def is_valid_error_code(code: str | None) -> bool:
    return code is None or code in ERROR_CODES
