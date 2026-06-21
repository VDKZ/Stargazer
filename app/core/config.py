from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_api: str = "https://api.github.com"
    request_timeout: float = 10.0

    # Scalability: bound the cost of a single request.
    max_stargazers: int = 500        # max number of stargazers analysed
    max_concurrency: int = 10        # concurrent HTTP calls (respects the rate limit)

    cache_ttl_seconds: int = 3600    # lifetime of a cache entry

    model_config = SettingsConfigDict(env_prefix="STARNEIGHBOURS_")


settings = Settings()