"""
Tests for Pydantic data models and validation.

This module tests all request/response models, validation logic,
data sanitization, and model factories.
"""

import pytest
from datetime import datetime, timedelta
from typing import List
from pydantic import ValidationError

from models.schemas import (
    # Request Models
    CreatePredictionRequest,
    PlaceBetRequest,
    ResolvePredictionRequest,
    VoteRequest,
    
    # Response Models
    PredictionResponse,
    BetResponse,
    MarketPricesResponse,
    MarketPriceInfo,
    UserBalanceResponse,
    ErrorResponse,
    ValidationErrorResponse,
    
    # Enums
    PredictionStatus,
    PredictionCategory,
    
    # Utilities
    SanitizedInput,
    ModelFactory
)


class TestCreatePredictionRequest:
    """Test CreatePredictionRequest validation"""
    
    def test_valid_prediction_request(self):
        """Test creating a valid prediction request"""
        request = CreatePredictionRequest(
            question="Will it rain tomorrow?",
            options=["Yes", "No"],
            duration_minutes=1440,
            category=PredictionCategory.WEATHER,
            initial_liquidity=10000
        )
        
        assert request.question == "Will it rain tomorrow?"
        assert request.options == ["Yes", "No"]
        assert request.duration_minutes == 1440
        assert request.category == PredictionCategory.WEATHER
        assert request.initial_liquidity == 10000
    
    def test_question_validation(self):
        """Test question field validation"""
        # Test empty question
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="",
                options=["Yes", "No"],
                duration_minutes=1440
            )
        assert "String should have at least 10 characters" in str(exc_info.value)
        
        # Test question too short
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Short?",
                options=["Yes", "No"],
                duration_minutes=1440
            )
        assert "at least 10 characters" in str(exc_info.value)
        
        # Test question too long
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="x" * 501,
                options=["Yes", "No"],
                duration_minutes=1440
            )
        assert "at most 500 characters" in str(exc_info.value)
        
        # Test inappropriate content
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Is this a spam question?",
                options=["Yes", "No"],
                duration_minutes=1440
            )
        assert "inappropriate content" in str(exc_info.value)
        
        # Test question mark addition
        request = CreatePredictionRequest(
            question="Will it rain tomorrow",
            options=["Yes", "No"],
            duration_minutes=1440
        )
        assert request.question == "Will it rain tomorrow?"
    
    def test_options_validation(self):
        """Test options field validation"""
        # Test too few options
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes"],
                duration_minutes=1440
            )
        assert "at least 2" in str(exc_info.value)
        
        # Test too many options
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="What will happen?",
                options=[f"Option {i}" for i in range(11)],
                duration_minutes=1440
            )
        assert "at most 10" in str(exc_info.value)
        
        # Test duplicate options removal
        request = CreatePredictionRequest(
            question="Will it rain tomorrow?",
            options=["Yes", "No", "yes", "YES", "Maybe"],
            duration_minutes=1440
        )
        assert len(request.options) == 3  # Yes, No, Maybe (duplicates removed)
        
        # Test empty options
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["", "No"],
                duration_minutes=1440
            )
        assert "At least 2 unique options are required" in str(exc_info.value)
        
        # Test option too long
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes", "x" * 101],
                duration_minutes=1440
            )
        assert "cannot exceed 100 characters" in str(exc_info.value)
    
    def test_duration_validation(self):
        """Test duration field validation"""
        # Test too short duration
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes", "No"],
                duration_minutes=1
            )
        assert "greater than 4" in str(exc_info.value)
        
        # Test too long duration
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes", "No"],
                duration_minutes=50000
            )
        assert "less than or equal to 43200" in str(exc_info.value)
    
    def test_initial_liquidity_validation(self):
        """Test initial liquidity validation"""
        # Test minimum liquidity
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes", "No"],
                duration_minutes=1440,
                initial_liquidity=500
            )
        assert "greater than or equal to 1000" in str(exc_info.value)
        
        # Test maximum liquidity
        with pytest.raises(ValidationError) as exc_info:
            CreatePredictionRequest(
                question="Will it rain tomorrow?",
                options=["Yes", "No"],
                duration_minutes=1440,
                initial_liquidity=2000000
            )
        assert "less than or equal to 1000000" in str(exc_info.value)


class TestPlaceBetRequest:
    """Test PlaceBetRequest validation"""
    
    def test_valid_bet_request(self):
        """Test creating a valid bet request"""
        request = PlaceBetRequest(
            prediction_id="test-prediction-1",
            option="Yes",
            amount=100
        )
        
        assert request.prediction_id == "test-prediction-1"
        assert request.option == "Yes"
        assert request.amount == 100
    
    def test_prediction_id_validation(self):
        """Test prediction ID validation"""
        # Test empty ID
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="",
                option="Yes",
                amount=100
            )
        assert "String should have at least 1 character" in str(exc_info.value)
        
        # Test invalid characters
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test@prediction#1",
                option="Yes",
                amount=100
            )
        assert "Invalid prediction ID format" in str(exc_info.value)
        
        # Test valid formats
        valid_ids = ["test-prediction-1", "test_prediction_1", "testprediction1", "123"]
        for valid_id in valid_ids:
            request = PlaceBetRequest(
                prediction_id=valid_id,
                option="Yes",
                amount=100
            )
            assert request.prediction_id == valid_id
    
    def test_option_validation(self):
        """Test option field validation"""
        # Test empty option
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test-prediction-1",
                option="",
                amount=100
            )
        assert "String should have at least 1 character" in str(exc_info.value)
        
        # Test invalid characters
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test-prediction-1",
                option="Yes<script>",
                amount=100
            )
        assert "invalid characters" in str(exc_info.value)
    
    def test_amount_validation(self):
        """Test amount field validation"""
        # Test zero amount
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test-prediction-1",
                option="Yes",
                amount=0
            )
        assert "greater than 0" in str(exc_info.value)
        
        # Test negative amount
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test-prediction-1",
                option="Yes",
                amount=-100
            )
        assert "greater than 0" in str(exc_info.value)
        
        # Test amount too large
        with pytest.raises(ValidationError) as exc_info:
            PlaceBetRequest(
                prediction_id="test-prediction-1",
                option="Yes",
                amount=2000000
            )
        assert "less than or equal to 1000000" in str(exc_info.value)


class TestResolvePredictionRequest:
    """Test ResolvePredictionRequest validation"""
    
    def test_valid_resolve_request(self):
        """Test creating a valid resolve request"""
        request = ResolvePredictionRequest(
            prediction_id="test-prediction-1",
            winning_option="Yes"
        )
        
        assert request.prediction_id == "test-prediction-1"
        assert request.winning_option == "Yes"
    
    def test_validation_errors(self):
        """Test validation errors"""
        # Test empty prediction ID
        with pytest.raises(ValidationError):
            ResolvePredictionRequest(
                prediction_id="",
                winning_option="Yes"
            )
        
        # Test empty winning option
        with pytest.raises(ValidationError):
            ResolvePredictionRequest(
                prediction_id="test-prediction-1",
                winning_option=""
            )


class TestVoteRequest:
    """Test VoteRequest validation"""
    
    def test_valid_vote_request(self):
        """Test creating a valid vote request"""
        request = VoteRequest(
            prediction_id="test-prediction-1",
            option="Yes"
        )
        
        assert request.prediction_id == "test-prediction-1"
        assert request.option == "Yes"


class TestResponseModels:
    """Test response models"""
    
    def test_prediction_response(self):
        """Test PredictionResponse model"""
        now = datetime.now()
        response = PredictionResponse(
            id="test-prediction-1",
            guild_id=123456789,
            question="Will it rain tomorrow?",
            options=["Yes", "No"],
            creator_id=987654321,
            status=PredictionStatus.ACTIVE,
            created_at=now,
            end_time=now + timedelta(days=1),
            initial_liquidity=10000,
            k_constant=100000000
        )
        
        assert response.id == "test-prediction-1"
        assert response.status == PredictionStatus.ACTIVE
        assert not response.resolved
        assert not response.refunded
    
    def test_bet_response(self):
        """Test BetResponse model"""
        response = BetResponse(
            id="test-bet-1",
            prediction_id="test-prediction-1",
            user_id=123456789,
            guild_id=987654321,
            option="Yes",
            amount=100,
            shares=95.0,
            price_per_share=1.05,
            created_at=datetime.now()
        )
        
        assert response.amount == 100
        assert response.shares == 95.0
        assert response.price_per_share == 1.05
    
    def test_market_price_info(self):
        """Test MarketPriceInfo model"""
        price_info = MarketPriceInfo(
            price_per_share=1.05,
            potential_shares=95.0,
            potential_payout=100,
            probability=52.5,
            total_bets=1000
        )
        
        assert price_info.price_per_share == 1.05
        assert price_info.probability == 52.5
    
    def test_market_prices_response(self):
        """Test MarketPricesResponse model"""
        prices = {
            "Yes": MarketPriceInfo(
                price_per_share=1.05,
                potential_shares=95.0,
                potential_payout=100,
                probability=52.5,
                total_bets=1000
            ),
            "No": MarketPriceInfo(
                price_per_share=0.95,
                potential_shares=105.0,
                potential_payout=100,
                probability=47.5,
                total_bets=800
            )
        }
        
        response = MarketPricesResponse(
            prediction_id="test-prediction-1",
            prices=prices
        )
        
        assert len(response.prices) == 2
        assert "Yes" in response.prices
        assert "No" in response.prices
    
    def test_error_response(self):
        """Test ErrorResponse model"""
        response = ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Invalid input provided",
            error_id="err-123456"
        )
        
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Invalid input provided"
        assert response.error_id == "err-123456"
        assert isinstance(response.timestamp, datetime)


class TestSanitizedInput:
    """Test input sanitization utilities"""
    
    def test_sanitize_text(self):
        """Test text sanitization"""
        # Test script injection removal
        dirty_text = "Hello <script>alert('xss')</script> world"
        clean_text = SanitizedInput.sanitize_text(dirty_text)
        assert "<script>" not in clean_text
        assert "alert" not in clean_text
        
        # Test excessive whitespace removal
        dirty_text = "Hello    world   with   spaces"
        clean_text = SanitizedInput.sanitize_text(dirty_text)
        assert clean_text == "Hello world with spaces"
        
        # Test control character removal
        dirty_text = "Hello\x00\x01world"
        clean_text = SanitizedInput.sanitize_text(dirty_text)
        assert "\x00" not in clean_text
        assert "\x01" not in clean_text
        
        # Test URL scheme removal
        dirty_text = "javascript:alert('xss')"
        clean_text = SanitizedInput.sanitize_text(dirty_text)
        assert "javascript:" not in clean_text
    
    def test_validate_discord_id(self):
        """Test Discord ID validation"""
        # Test valid Discord IDs
        valid_ids = [123456789012345678, "123456789012345678"]
        for valid_id in valid_ids:
            result = SanitizedInput.validate_discord_id(valid_id)
            assert isinstance(result, int)
            assert result > 0
        
        # Test invalid Discord IDs
        invalid_ids = [0, -1, "abc", "123", "12345678901234567890123"]
        for invalid_id in invalid_ids:
            with pytest.raises(ValueError):
                SanitizedInput.validate_discord_id(invalid_id)


class TestModelFactory:
    """Test model factory for creating test instances"""
    
    def test_create_prediction_request(self):
        """Test creating prediction request via factory"""
        request = ModelFactory.create_prediction_request()
        
        assert isinstance(request, CreatePredictionRequest)
        assert request.question == "Will it rain tomorrow?"
        assert request.options == ["Yes", "No"]
        assert request.duration_minutes == 1440
        
        # Test with custom parameters
        custom_request = ModelFactory.create_prediction_request(
            question="Will the stock go up?",
            options=["Up", "Down", "Sideways"],
            duration_minutes=720,
            category=PredictionCategory.CRYPTO
        )
        
        assert custom_request.question == "Will the stock go up?"
        assert len(custom_request.options) == 3
        assert custom_request.category == PredictionCategory.CRYPTO
    
    def test_create_bet_request(self):
        """Test creating bet request via factory"""
        request = ModelFactory.create_bet_request()
        
        assert isinstance(request, PlaceBetRequest)
        assert request.prediction_id == "test-prediction-1"
        assert request.option == "Yes"
        assert request.amount == 100
    
    def test_create_resolve_request(self):
        """Test creating resolve request via factory"""
        request = ModelFactory.create_resolve_request()
        
        assert isinstance(request, ResolvePredictionRequest)
        assert request.prediction_id == "test-prediction-1"
        assert request.winning_option == "Yes"
    
    def test_create_vote_request(self):
        """Test creating vote request via factory"""
        request = ModelFactory.create_vote_request()
        
        assert isinstance(request, VoteRequest)
        assert request.prediction_id == "test-prediction-1"
        assert request.option == "Yes"
    
    def test_create_prediction_response(self):
        """Test creating prediction response via factory"""
        response = ModelFactory.create_prediction_response()
        
        assert isinstance(response, PredictionResponse)
        assert response.id == "test-prediction-1"
        assert response.status == PredictionStatus.ACTIVE
        assert not response.resolved
    
    def test_create_bet_response(self):
        """Test creating bet response via factory"""
        response = ModelFactory.create_bet_response()
        
        assert isinstance(response, BetResponse)
        assert response.id == "test-bet-1"
        assert response.amount == 100
        assert response.shares == 95.0
    
    def test_create_market_prices_response(self):
        """Test creating market prices response via factory"""
        response = ModelFactory.create_market_prices_response()
        
        assert isinstance(response, MarketPricesResponse)
        assert response.prediction_id == "test-prediction-1"
        assert len(response.prices) == 2
        assert "Yes" in response.prices
        assert "No" in response.prices
    
    def test_create_error_response(self):
        """Test creating error response via factory"""
        response = ModelFactory.create_error_response()
        
        assert isinstance(response, ErrorResponse)
        assert response.error_code == "VALIDATION_ERROR"
        assert response.message == "Invalid input provided"
        assert response.error_id == "err-123456"


class TestEnums:
    """Test enum definitions"""
    
    def test_prediction_status_enum(self):
        """Test PredictionStatus enum"""
        assert PredictionStatus.ACTIVE == "active"
        assert PredictionStatus.RESOLVED == "resolved"
        assert PredictionStatus.REFUNDED == "refunded"
        assert PredictionStatus.CANCELLED == "cancelled"
    
    def test_prediction_category_enum(self):
        """Test PredictionCategory enum"""
        assert PredictionCategory.GENERAL == "general"
        assert PredictionCategory.SPORTS == "sports"
        assert PredictionCategory.POLITICS == "politics"
        assert PredictionCategory.ENTERTAINMENT == "entertainment"
        assert PredictionCategory.TECHNOLOGY == "technology"
        assert PredictionCategory.CRYPTO == "crypto"
        assert PredictionCategory.WEATHER == "weather"
        assert PredictionCategory.OTHER == "other"


class TestEdgeCases:
    """Test edge cases and boundary conditions"""
    
    def test_whitespace_handling(self):
        """Test whitespace handling in various fields"""
        # Test question with leading/trailing whitespace
        request = CreatePredictionRequest(
            question="  Will it rain tomorrow?  ",
            options=["  Yes  ", "  No  "],
            duration_minutes=1440
        )
        
        assert request.question == "Will it rain tomorrow?"
        assert request.options == ["Yes", "No"]
    
    def test_unicode_handling(self):
        """Test Unicode character handling"""
        request = CreatePredictionRequest(
            question="Will it rain tomorrow? 🌧️",
            options=["Yes ✅", "No ❌"],
            duration_minutes=1440
        )
        
        assert "🌧️" in request.question
        assert "✅" in request.options[0]
        assert "❌" in request.options[1]
    
    def test_boundary_values(self):
        """Test boundary values for numeric fields"""
        # Test minimum valid duration
        request = CreatePredictionRequest(
            question="Will it rain tomorrow?",
            options=["Yes", "No"],
            duration_minutes=5
        )
        assert request.duration_minutes == 5
        
        # Test maximum valid duration
        request = CreatePredictionRequest(
            question="Will it rain tomorrow?",
            options=["Yes", "No"],
            duration_minutes=43200
        )
        assert request.duration_minutes == 43200
        
        # Test minimum valid bet amount
        request = PlaceBetRequest(
            prediction_id="test-prediction-1",
            option="Yes",
            amount=1
        )
        assert request.amount == 1
        
        # Test maximum valid bet amount
        request = PlaceBetRequest(
            prediction_id="test-prediction-1",
            option="Yes",
            amount=1000000
        )
        assert request.amount == 1000000


if __name__ == "__main__":
    pytest.main([__file__])