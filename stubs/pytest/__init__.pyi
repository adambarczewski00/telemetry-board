from typing import Optional

class MonkeyPatch:
    def setenv(
        self, name: str, value: str, *, prepend: Optional[str] = None
    ) -> None: ...
    def delenv(self, name: str, *, raising: bool = True) -> None: ...
