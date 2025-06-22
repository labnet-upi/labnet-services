from pydantic import BaseSettings

class Settings(BaseSettings):
    mongo_username: str
    mongo_password: str
    mongo_host: str = "localhost"
    mongo_port: int = 27017
    mongo_db: str
    mongo_auth_db: str = "admin"

    @property
    def mongo_uri(self):
        return f"mongodb://{self.mongo_username}:{self.mongo_password}@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource={self.mongo_auth_db}"

    class Config:
        env_file = ".env"
