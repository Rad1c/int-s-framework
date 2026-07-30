"""
Framework settings loaded from environment variables / .env.

Services subclass FrameworkSettings and add their own fields:

    class Settings(FrameworkSettings):
        service_type: str = "betbox_service"
        rabbitmq_request_queue: str = "requests.betbox"
        betbox_api_base_url: str = "https://..."
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class FrameworkSettings(BaseSettings):
    # Identity
    service_name: str = "Integration Service"
    # serviceType this instance handles; messages with a different serviceType are ignored.
    service_type: str

    # RabbitMQ connection
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    # Betbox used RABBITMQ_USERNAME, internal backoffice RABBITMQ_USER — accept both.
    rabbitmq_user: str = Field(
        default="guest",
        validation_alias=AliasChoices("rabbitmq_user", "rabbitmq_username"),
    )
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    rabbitmq_heartbeat: int = 600
    rabbitmq_connection_timeout: int = 10

    # Request/response pipeline: requests are fanned out from the request
    # exchange (request_topic) to a per-service queue (request_queue);
    # response envelopes go to the response topic with correlation headers.
    rabbitmq_request_topic: str = "requests"
    rabbitmq_request_queue: str
    rabbitmq_response_topic: str = "responses"

    consumer_prefetch_count: int = 10

    # Outer reconnect loop (initial connection failures; once connected,
    # aio-pika RobustConnection handles reconnects on its own).
    rabbitmq_max_retry_attempts: int = 0  # 0 = retry forever
    rabbitmq_initial_retry_delay: float = 1.0
    rabbitmq_max_retry_delay: float = 60.0
    rabbitmq_retry_backoff_multiplier: float = 2.0

    # HTTP server
    http_port: int = 8080

    # Logging
    log_level: str = "INFO"
    log_file: str = ""  # empty = console only
    log_retention_days: int = 7

    # 'development' enables the /debug endpoints.
    app_env: str = ""

    model_config = {"env_file": ".env", "case_sensitive": False, "extra": "ignore"}

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"
