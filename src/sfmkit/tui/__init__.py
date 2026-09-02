"""Terminal UI for browsing and comparing runs.

Strictly a client. Everything the TUI shows, the CLI can print, and everything
it can do, the CLI can do -- it adds convenience, never capability. If a feature
were reachable only from here it would be a second implementation, which is the
same mistake as the original project's COLMAP export living only in a notebook.

It reads the manifests each stage writes; it does not shell out to the CLI and
parse its output, and it does not reimplement any of the library.
"""

from sfmkit.tui.app import SfmkitApp, run

__all__ = ["SfmkitApp", "run"]
