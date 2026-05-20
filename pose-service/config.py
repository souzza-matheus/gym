from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    tf_serving_host: str = "tf-serving"
    tf_serving_port: int = 8500
    model_name: str = "movenet_thunder"
    min_confidence: float = 0.5
    host: str = "0.0.0.0"
    port: int = 8083

    rabbitmq_host: str = "rabbitmq"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "gymvision"
    rabbitmq_pass: str = "gymvision123"

    class Config:
        env_file = ".env"


settings = Settings()
