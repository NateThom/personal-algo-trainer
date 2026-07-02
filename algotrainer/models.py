from dataclasses import dataclass


@dataclass(frozen=True)
class TestCase:
    args: list
    expected: object


@dataclass(frozen=True)
class Problem:
    id: str
    pattern: str
    title: str
    difficulty: str
    statement: str
    function_name: str
    starter_code: str
    reference_solution: str
    tests: list[TestCase]
    hints: list[str]

    @classmethod
    def from_dict(cls, d: dict) -> "Problem":
        tests = [TestCase(args=t["args"], expected=t["expected"]) for t in d["tests"]]
        return cls(
            id=d["id"],
            pattern=d["pattern"],
            title=d["title"],
            difficulty=d["difficulty"],
            statement=d["statement"],
            function_name=d["function_name"],
            starter_code=d["starter_code"],
            reference_solution=d["reference_solution"],
            tests=tests,
            hints=list(d.get("hints", [])),
        )
