"""Everything that touches the filesystem, plus configuration.

Keeping I/O in one layer is the discipline whose absence broke the first
version of this project: there, geometry functions loaded their own inputs from
hardcoded relative paths, so stages could not be re-run, re-pointed, or tested.
"""
