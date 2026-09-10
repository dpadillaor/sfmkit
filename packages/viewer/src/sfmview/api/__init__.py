"""HTTP: the JSON API and the web page. It sees the ports, never an adapter."""

from sfmview.api.app import create_app

__all__ = ["create_app"]
