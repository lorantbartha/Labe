from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    goals_table: str
    openai_api_key: str
    openai_fast_model: str = "gpt-5-mini"
    openai_reasoning_model: str = "gpt-5.1"
    aws_endpoint_url: str | None = None
    aws_default_region: str = "us-east-1"

    @property
    def aws_region(self) -> str:
        return self.aws_default_region


# Pyright cannot see pydantic-settings env binding; required fields are satisfied at runtime from env / .env.
app_config = AppConfig()  # pyright: ignore[reportCallIssue]
