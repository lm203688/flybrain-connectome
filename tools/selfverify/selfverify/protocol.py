"""Protocol model: a preregistration record + the four verdict classes.

The four classes (see README) are the whole point: a preregistered study can
end in SUCCESS, FAILURE, WEAK, or — the class most tools miss —
PRE_EXECUTION_REJECTION (a metric was refused *before* running because it was
analytically redundant).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Verdict(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    WEAK = "WEAK"
    PRE_EXECUTION_REJECTION = "PRE_EXECUTION_REJECTION"


@dataclass
class Protocol:
    """A frozen preregistration record.

    Fields mirror what the gate needs; unknown keys in the JSON are ignored so
    the schema can grow without breaking older records.
    """

    id: str
    hypothesis: str
    metric: str
    features: list = field(default_factory=list)
    success_criteria: dict = field(default_factory=dict)
    train_slice: str = ""
    held_out_slice: str = ""
    reject_rules: list = field(default_factory=list)
    label_definition: str = ""
    registered_at: str = ""

    @classmethod
    def load(cls, path: str | Path) -> "Protocol":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}
