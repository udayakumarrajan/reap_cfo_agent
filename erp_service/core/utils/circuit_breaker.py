import time
from enum import Enum
from loguru import logger

class State(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """
    Production-ready Circuit Breaker pattern implementation.
    Follows SRP by managing internal state independently of the service logic.
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = State.CLOSED
        self.failures = 0
        self.last_failure_time = 0

    def is_available(self) -> bool:
        """Checks if the circuit is available for a call."""
        if self.state == State.OPEN:
            # Check if recovery timeout has passed
            elapsed = time.time() - self.last_failure_time
            if elapsed > self.recovery_timeout:
                logger.info(f"CircuitBreaker: Recovery timeout ({self.recovery_timeout}s) reached. Transitioning to HALF_OPEN.")
                self.state = State.HALF_OPEN
                return True
            return False
        return True

    def record_success(self):
        """Resets the circuit upon a successful call."""
        if self.state != State.CLOSED:
            logger.success(f"CircuitBreaker: Success detected. Closing circuit. State was {self.state.value}.")
        self.state = State.CLOSED
        self.failures = 0

    def record_failure(self):
        """Increments failure count and opens circuit if threshold reached."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == State.HALF_OPEN:
            logger.warning("CircuitBreaker: Failure in HALF_OPEN state. Immediately re-opening circuit.")
            self.state = State.OPEN
        elif self.failures >= self.failure_threshold:
            logger.error(f"CircuitBreaker: Failure threshold ({self.failure_threshold}) reached. Opening circuit for {self.recovery_timeout}s.")
            self.state = State.OPEN

    @property
    def current_state(self) -> str:
        return self.state.value
