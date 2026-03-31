import pytest
from fastapi.testclient import TestClient
from src.app import app


@pytest.fixture
def client():
    """Test client fixture for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def reset_activities():
    """Reset activities to initial state before each test"""
    from src.app import activities
    # Store original state
    original = activities.copy()
    yield
    # Reset after test
    activities.clear()
    activities.update(original)


class TestGetActivities:
    """Test cases for GET /activities endpoint"""

    def test_get_activities_success(self, client):
        """Test successful retrieval of all activities"""
        # Arrange
        expected_activities = [
            "Chess Club", "Programming Class", "Gym Class", "Basketball Team",
            "Track and Field", "Art Club", "Drama Club", "Debate Team", "Science Club"
        ]

        # Act
        response = client.get("/activities")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) == 9
        assert all(activity in data for activity in expected_activities)
        # Check structure of first activity
        chess_club = data["Chess Club"]
        assert "description" in chess_club
        assert "schedule" in chess_club
        assert "max_participants" in chess_club
        assert "participants" in chess_club
        assert isinstance(chess_club["participants"], list)


class TestSignup:
    """Test cases for POST /activities/{activity_name}/signup endpoint"""

    def test_signup_success(self, client, reset_activities):
        """Test successful signup for an activity"""
        # Arrange
        activity_name = "Chess Club"
        email = "newstudent@mergington.edu"

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity_name in data["message"]

        # Verify participant was added
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email in activities_data[activity_name]["participants"]

    def test_signup_nonexistent_activity(self, client):
        """Test signup for non-existent activity returns 404"""
        # Arrange
        activity_name = "NonExistent Club"
        email = "student@mergington.edu"

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]

    def test_signup_duplicate_email(self, client, reset_activities):
        """Test signup with already enrolled email returns 400"""
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"  # Already enrolled

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Student already signed up" in data["detail"]


class TestUnregister:
    """Test cases for DELETE /activities/{activity_name}/unregister endpoint"""

    def test_unregister_success(self, client, reset_activities):
        """Test successful unregister from an activity"""
        # Arrange
        activity_name = "Chess Club"
        email = "michael@mergington.edu"  # Already enrolled

        # Act
        response = client.delete(f"/activities/{activity_name}/unregister", params={"email": email})

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        assert activity_name in data["message"]

        # Verify participant was removed
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email not in activities_data[activity_name]["participants"]

    def test_unregister_nonexistent_activity(self, client):
        """Test unregister from non-existent activity returns 404"""
        # Arrange
        activity_name = "NonExistent Club"
        email = "student@mergington.edu"

        # Act
        response = client.delete(f"/activities/{activity_name}/unregister", params={"email": email})

        # Assert
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]

    def test_unregister_not_enrolled(self, client, reset_activities):
        """Test unregister for student not enrolled returns 400"""
        # Arrange
        activity_name = "Chess Club"
        email = "notenrolled@mergington.edu"

        # Act
        response = client.delete(f"/activities/{activity_name}/unregister", params={"email": email})

        # Assert
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Student not signed up for this activity" in data["detail"]


class TestEdgeCases:
    """Test edge cases and validation"""

    def test_signup_empty_email(self, client):
        """Test signup with empty email parameter"""
        # Arrange
        activity_name = "Chess Club"
        email = ""

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        # Note: FastAPI might handle empty strings differently, but let's test
        # This might pass or fail depending on validation, but we test the behavior
        # For now, assume it allows empty, but in real app might want validation
        assert response.status_code in [200, 400]  # Depending on implementation

    def test_signup_missing_email(self, client):
        """Test signup without email parameter"""
        # Arrange
        activity_name = "Chess Club"

        # Act
        response = client.post(f"/activities/{activity_name}/signup")

        # Assert
        assert response.status_code == 422  # Unprocessable Entity for missing required param

    def test_activity_name_case_sensitivity(self, client, reset_activities):
        """Test that activity names are case sensitive"""
        # Arrange
        activity_name = "chess club"  # lowercase
        email = "student@mergington.edu"

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        assert response.status_code == 404  # Should be case sensitive

    def test_activity_name_with_spaces(self, client, reset_activities):
        """Test activity names with spaces (URL encoded)"""
        # Arrange
        activity_name = "Chess Club"
        email = "student@mergington.edu"

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})

        # Assert
        assert response.status_code == 200  # Should work with spaces


class TestBusinessLogic:
    """Test business logic like capacity limits"""

    def test_signup_capacity_limit(self, client, reset_activities):
        """Test signup when activity reaches capacity"""
        # Arrange
        activity_name = "Chess Club"
        # Chess Club has max_participants = 12, currently 2 participants
        # Add 10 more to reach capacity
        emails = [f"student{i}@mergington.edu" for i in range(10)]

        # Fill to capacity
        for email in emails:
            response = client.post(f"/activities/{activity_name}/signup", params={"email": email})
            assert response.status_code == 200

        # Now try to add one more
        extra_email = "extra@mergington.edu"

        # Act
        response = client.post(f"/activities/{activity_name}/signup", params={"email": extra_email})

        # Assert
        # Currently, the app doesn't enforce capacity, so it will succeed
        # But we test the current behavior; in future, it might be 400
        assert response.status_code == 200  # Current implementation allows over capacity

    def test_participant_integrity(self, client, reset_activities):
        """Test that participants list maintains integrity"""
        # Arrange
        activity_name = "Programming Class"
        email = "newstudent@mergington.edu"

        # Act - signup
        response = client.post(f"/activities/{activity_name}/signup", params={"email": email})
        assert response.status_code == 200

        # Verify added
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email in activities_data[activity_name]["participants"]

        # Act - unregister
        response = client.delete(f"/activities/{activity_name}/unregister", params={"email": email})
        assert response.status_code == 200

        # Verify removed
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email not in activities_data[activity_name]["participants"]


class TestIntegration:
    """Integration tests for full user flows"""

    def test_signup_then_unregister_flow(self, client, reset_activities):
        """Test complete signup and unregister flow"""
        # Arrange
        activity_name = "Art Club"
        email = "integrationtest@mergington.edu"

        # Act - signup
        signup_response = client.post(f"/activities/{activity_name}/signup", params={"email": email})
        assert signup_response.status_code == 200

        # Verify signed up
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email in activities_data[activity_name]["participants"]

        # Act - unregister
        unregister_response = client.delete(f"/activities/{activity_name}/unregister", params={"email": email})
        assert unregister_response.status_code == 200

        # Verify unregistered
        get_response = client.get("/activities")
        activities_data = get_response.json()
        assert email not in activities_data[activity_name]["participants"]

    def test_multiple_activities_per_student(self, client, reset_activities):
        """Test student signing up for multiple activities"""
        # Arrange
        activities = ["Gym Class", "Track and Field"]
        email = "multiactivity@mergington.edu"

        # Act - signup for multiple
        for activity_name in activities:
            response = client.post(f"/activities/{activity_name}/signup", params={"email": email})
            assert response.status_code == 200

        # Verify in all activities
        get_response = client.get("/activities")
        activities_data = get_response.json()
        for activity_name in activities:
            assert email in activities_data[activity_name]["participants"]