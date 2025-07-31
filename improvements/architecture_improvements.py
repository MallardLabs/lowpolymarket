"""
Architecture Improvements for Prediction Market Bot
"""

from abc import ABC, abstractmethod
from typing import Protocol, TypeVar, Generic
from dataclasses import dataclass
from enum import Enum
import asyncio
from contextlib import asynccontextmanager

# 1. DEPENDENCY INJECTION PATTERN
class DatabaseProtocol(Protocol):
    async def get_prediction(self, prediction_id: str) -> dict: ...
    async def place_bet(self, bet_data: dict) -> bool: ...

class PointsManagerProtocol(Protocol):
    async def get_balance(self, user_id: int) -> int: ...
    async def transfer_points(self, from_id: int, to_id: int, amount: int) -> bool: ...

# 2. DOMAIN MODELS WITH VALIDATION
@dataclass(frozen=True)
class BetRequest:
    user_id: int
    prediction_id: str
    option: str
    amount: int
    
    def __post_init__(self):
        if self.amount <= 0:
            raise ValueError("Bet amount must be positive")
        if not self.option.strip():
            raise ValueError("Option cannot be empty")

@dataclass(frozen=True)
class MarketState:
    prediction_id: str
    liquidity_pools: dict[str, int]
    total_volume: int
    status: str
    
    @property
    def is_active(self) -> bool:
        return self.status == 'active'

# 3. COMMAND PATTERN FOR OPERATIONS
class Command(ABC):
    @abstractmethod
    async def execute(self) -> bool: ...
    
    @abstractmethod
    async def rollback(self) -> bool: ...

class PlaceBetCommand(Command):
    def __init__(self, bet_request: BetRequest, db: DatabaseProtocol, points: PointsManagerProtocol):
        self.bet_request = bet_request
        self.db = db
        self.points = points
        self._executed = False
        
    async def execute(self) -> bool:
        # Atomic operation with rollback capability
        try:
            # Deduct points first
            success = await self.points.transfer_points(
                self.bet_request.user_id, 
                0,  # Bot account
                self.bet_request.amount
            )
            if not success:
                return False
                
            # Place bet in database
            success = await self.db.place_bet(self.bet_request.__dict__)
            if not success:
                await self.rollback()
                return False
                
            self._executed = True
            return True
            
        except Exception:
            await self.rollback()
            raise
    
    async def rollback(self) -> bool:
        if self._executed:
            # Refund points
            return await self.points.transfer_points(
                0, 
                self.bet_request.user_id, 
                self.bet_request.amount
            )
        return True

# 4. REPOSITORY PATTERN
class PredictionRepository(ABC):
    @abstractmethod
    async def find_by_id(self, prediction_id: str) -> Optional['Prediction']: ...
    
    @abstractmethod
    async def find_active_by_guild(self, guild_id: int) -> List['Prediction']: ...
    
    @abstractmethod
    async def save(self, prediction: 'Prediction') -> bool: ...

class SupabasePredictionRepository(PredictionRepository):
    def __init__(self, db_manager):
        self.db = db_manager
    
    async def find_by_id(self, prediction_id: str) -> Optional['Prediction']:
        data = await self.db.get_prediction_by_id(prediction_id)
        return Prediction.from_dict(data) if data else None
    
    async def find_active_by_guild(self, guild_id: int) -> List['Prediction']:
        data_list = await self.db.get_active_predictions(guild_id)
        return [Prediction.from_dict(data) for data in data_list]

# 5. SERVICE LAYER
class PredictionService:
    def __init__(self, 
                 repo: PredictionRepository, 
                 points_manager: PointsManagerProtocol,
                 event_bus: 'EventBus'):
        self.repo = repo
        self.points_manager = points_manager
        self.event_bus = event_bus
    
    async def place_bet(self, bet_request: BetRequest) -> Result[bool, str]:
        """Place a bet with proper validation and error handling"""
        try:
            # Validate user has sufficient balance
            balance = await self.points_manager.get_balance(bet_request.user_id)
            if balance < bet_request.amount:
                return Result.error("Insufficient balance")
            
            # Get prediction
            prediction = await self.repo.find_by_id(bet_request.prediction_id)
            if not prediction:
                return Result.error("Prediction not found")
            
            if not prediction.is_active():
                return Result.error("Prediction is not active")
            
            # Execute bet command
            command = PlaceBetCommand(bet_request, self.repo, self.points_manager)
            success = await command.execute()
            
            if success:
                # Publish event for real-time updates
                await self.event_bus.publish(BetPlacedEvent(bet_request))
                return Result.success(True)
            else:
                return Result.error("Failed to place bet")
                
        except Exception as e:
            return Result.error(f"Unexpected error: {str(e)}")

# 6. RESULT TYPE FOR ERROR HANDLING
T = TypeVar('T')
E = TypeVar('E')

class Result(Generic[T, E]):
    def __init__(self, value: T = None, error: E = None):
        self._value = value
        self._error = error
    
    @classmethod
    def success(cls, value: T) -> 'Result[T, E]':
        return cls(value=value)
    
    @classmethod
    def error(cls, error: E) -> 'Result[T, E]':
        return cls(error=error)
    
    @property
    def is_success(self) -> bool:
        return self._error is None
    
    @property
    def value(self) -> T:
        if self._error is not None:
            raise ValueError("Cannot get value from error result")
        return self._value
    
    @property
    def error(self) -> E:
        if self._error is None:
            raise ValueError("Cannot get error from success result")
        return self._error

# 7. EVENT-DRIVEN ARCHITECTURE
class Event(ABC):
    pass

@dataclass
class BetPlacedEvent(Event):
    bet_request: BetRequest
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', time.time())

class EventBus:
    def __init__(self):
        self._handlers: dict[type, list] = {}
    
    def subscribe(self, event_type: type, handler):
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
    
    async def publish(self, event: Event):
        handlers = self._handlers.get(type(event), [])
        await asyncio.gather(*[handler(event) for handler in handlers])