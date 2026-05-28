import os
from dotenv import load_dotenv

load_dotenv()


class RedshiftConfig:
    def __init__(self):
        self.host = os.getenv(
            "REDSHIFT_HOST", "campus-cluster.cnpxyz.us-east-1.redshift.amazonaws.com"
        )
        self.port = int(os.getenv("REDSHIFT_PORT", "5439"))
        self.database = os.getenv("REDSHIFT_DATABASE", "analytics")
        self.user = os.getenv("REDSHIFT_USER", "admin")
        self.password = os.getenv("REDSHIFT_PASSWORD", "")
        self.schema = os.getenv("REDSHIFT_SCHEMA", "public")

    def get_connection_string(self):
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
