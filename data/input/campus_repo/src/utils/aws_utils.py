import psycopg2
from contextlib import contextmanager
import boto3
import json
from src.config.redshift_config import RedshiftConfig


class RedshiftConnector:
    def __init__(self, config=None):
        self.config = config or RedshiftConfig()

    @contextmanager
    def get_connection(self):
        conn = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            user=self.config.user,
            password=self.config.password,
            connect_timeout=10,
        )
        try:
            yield conn
        finally:
            if conn:
                conn.close()

    def execute_query(self, query, params=None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return cursor.fetchall()


class S3Handler:
    def __init__(self, bucket_name):
        self.bucket_name = bucket_name
        self.s3_client = boto3.client("s3")

    def read_json(self, key):
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response["Body"].read())
        except Exception as e:
            raise Exception(f"Failed to read {key} from {self.bucket_name}: {str(e)}")

    def write_json(self, key, data):
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(data),
                ContentType="application/json",
            )
        except Exception as e:
            raise Exception(f"Failed to write {key} to {self.bucket_name}: {str(e)}")

    def list_objects(self, prefix):
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name, Prefix=prefix
        )
        return [obj["Key"] for obj in response.get("Contents", [])]
