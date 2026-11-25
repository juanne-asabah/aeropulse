"""
AeroPulse - Comprehensive Test Suite
====================================
Tests API endpoints, in-memory caching, load balancing headers,
input validation, filtering, sorting, and error resilience using
Python's built-in unittest framework (zero dependencies).
"""

import unittest
import os
import sys

# Ensure summative root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app, cache

class TestAeroPulseAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        cache.clear()

    def test_01_health_check_endpoint(self):
        """Verify health check returns HTTP 200, healthy status, and server metadata."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "healthy")
        self.assertIn("server_id", data)
        self.assertIn("uptime_seconds", data)
        self.assertIn("cache", data)

    def test_02_custom_server_identification_headers(self):
        """Verify X-Served-By and security headers are injected in all responses."""
        response = self.client.get("/api/health")
        self.assertIn("X-Served-By", response.headers)
        self.assertIn("X-Response-Time-Ms", response.headers)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_03_cities_endpoint_and_summary(self):
        """Verify /api/cities returns city list and summary statistics."""
        response = self.client.get("/api/cities")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("cities", data)
        self.assertIn("summary", data)
        self.assertGreaterEqual(len(data["cities"]), 1)

    def test_04_city_filtering_by_category(self):
        """Verify /api/cities?category=good filters correctly."""
        response = self.client.get("/api/cities?category=good")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        for city in data["cities"]:
            self.assertEqual(city["category"].lower(), "good")

    def test_05_city_sorting_by_aqi(self):
        """Verify /api/cities?sort_by=aqi_asc sorts correctly."""
        response = self.client.get("/api/cities?sort_by=aqi_asc")
        self.assertEqual(response.status_code, 200)
        cities = response.get_json()["cities"]
        aqis = [c["aqi_us"] for c in cities]
        self.assertEqual(aqis, sorted(aqis))

    def test_06_in_memory_ttl_caching(self):
        """Verify repeated calls hit cache instead of external APIs."""
        stats_before = cache.stats()
        
        # First fetch: populates cache
        self.client.get("/api/cities")
        
        # Second fetch: serves from cache
        self.client.get("/api/cities")
        stats_second = cache.stats()
        
        self.assertGreater(stats_second["total_hits"], stats_before["total_hits"])

    def test_07_search_missing_parameter_bad_request(self):
        """Verify /api/search without 'q' parameter returns HTTP 400 Bad Request."""
        response = self.client.get("/api/search")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_08_compare_missing_parameter_bad_request(self):
        """Verify /api/compare without both cities returns HTTP 400 Bad Request."""
        response = self.client.get("/api/compare?city1=Tokyo")
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertIn("error", data)

    def test_09_unhealthy_filter_excludes_sensitive(self):
        """Unhealthy filter must only return AQI 151 and above."""
        response = self.client.get("/api/cities?category=unhealthy")
        self.assertEqual(response.status_code, 200)
        for c in response.get_json()["cities"]:
            self.assertGreaterEqual(c["aqi_us"], 151)

if __name__ == "__main__":
    unittest.main()
