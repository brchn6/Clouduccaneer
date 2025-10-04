"""Tests for web UI module."""

import pytest


class TestWebModule:
    """Tests for web module availability."""

    def test_web_module_imports(self):
        """Test that web module can be imported."""
        from cb.web import app as web_app
        assert web_app is not None

    def test_web_app_imports(self):
        """Test that FastAPI app can be imported."""
        from cb.web.app import app
        assert app is not None
        assert app.title == "CloudBuccaneer Web UI"
        assert app.version == "0.1.0"

    def test_web_routes_exist(self):
        """Test that main routes are registered."""
        from cb.web.app import app
        
        routes = [route.path for route in app.routes]
        
        # Check essential routes exist
        assert "/" in routes
        assert "/api/config" in routes
        assert "/api/fetch" in routes
        assert "/api/search" in routes
        assert "/api/rename" in routes
        assert "/api/clean" in routes
        assert "/api/bpm" in routes
