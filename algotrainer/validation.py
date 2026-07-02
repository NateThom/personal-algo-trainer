"""Single source of the problem self-consistency rule: a problem's reference
solution must return each test's expected value. Used by seed loading and by
AI-variant acceptance."""
from algotrainer.models import Problem


def validate_problem_dict(d: dict) -> tuple[bool, str | None]:
    try:
        p = Problem.from_dict(d)
    except Exception as e:  # missing keys / bad shape
        return False, f"bad problem shape: {e}"
    namespace: dict = {}
    try:
        exec(p.reference_solution, namespace)  # noqa: S102 - trusted/generated content, validated here
    except Exception as e:
        return False, f"reference_solution failed to define: {e}"
    fn = namespace.get(p.function_name)
    if fn is None:
        return False, f"reference_solution does not define {p.function_name!r}"
    for tc in p.tests:
        try:
            got = fn(*tc.args)
        except Exception as e:
            return False, f"reference_solution raised on args {tc.args!r}: {e}"
        if got != tc.expected:
            return False, f"mismatch on args {tc.args!r}: got {got!r}, expected {tc.expected!r}"
    return True, None
