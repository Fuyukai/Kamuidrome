from typing import Literal

import attr
import cattr

type BootlegEnum = Literal[1, 2, 3]


@attr.s()
class UsesBootlegEnum:  # noqa: D101
    tag: BootlegEnum = attr.ib()


cattr.structure({"tag": 1}, UsesBootlegEnum)
