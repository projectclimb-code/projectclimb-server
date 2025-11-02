from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import Group, Venue, Route # Import some models to test

# It's good practice to create some test data, but for this initial check,
# we'll just ensure the endpoints are registered and return 200 or 404 if no data.

class GroupAPITests(APITestCase):
    def test_list_groups(self):
        """
        Ensure we can list groups.
        """
        url = reverse('group-list') # DefaultRouter names are modelname-list
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class VenueAPITests(APITestCase):
    def test_list_venues(self):
        """
        Ensure we can list venues.
        """
        url = reverse('venue-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class RouteAPITests(APITestCase):
    def test_list_routes(self):
        """
        Ensure we can list routes.
        """
        url = reverse('route-list')
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

# TODO: Add tests for other models (AppUser, Wall, Hold)
# TODO: Add tests for create, retrieve, update, delete operations
# TODO: Add tests for permissions if they become more complex
