import os
import logging
from typing import List
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

from .models import ChatMessage

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DynamoDBClient:
    """Client for interacting with AWS DynamoDB for chat history."""

    def __init__(self):
        """Initialize the DynamoDB client and table."""
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.table_name = os.getenv("DYNAMODB_CHAT_MESSAGE_TABLE", "chat_messages")

        try:
            self.dynamodb = boto3.resource("dynamodb", region_name=self.region)
            self.table = self.dynamodb.Table(self.table_name)

            # Check if table exists by describing it
            self.table.load()
            logger.info(f"Connected to existing DynamoDB table: {self.table_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info("DynamoDB table not found. Creating new table...")
                self._create_table()
            else:
                logger.error(f"Failed to connect to DynamoDB: {e}")
                raise

    def _create_table(self):
        """Create DynamoDB table with user_id as partition key and timestamp as sort key."""
        try:
            table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {"AttributeName": "user_id", "KeyType": "HASH"},  # Partition key
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},  # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "user_id", "AttributeType": "S"},
                    {"AttributeName": "timestamp", "AttributeType": "S"},
                ],
                BillingMode="PAY_PER_REQUEST",  # Serverless on-demand pricing
            )

            table.wait_until_exists()
            self.table = table
            logger.info(f"Created DynamoDB table: {self.table_name}")

        except Exception as e:
            logger.error(f"Failed to create DynamoDB table: {e}")
            raise

    # ------------------------------------------------------------------
    # CRUD OPERATIONS
    # ------------------------------------------------------------------

    def save_message(self, message: ChatMessage) -> bool:
        """Save a message to DynamoDB."""
        try:
            item = message.to_dict()

            # Ensure timestamp is string (required for DynamoDB sort key)
            if isinstance(item.get("timestamp"), datetime):
                item["timestamp"] = item["timestamp"].isoformat()

            self.table.put_item(Item=item)

            logger.info(f"Message saved for user {message.user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False

    def get_user_messages(self, user_id: str, limit: int = 100) -> List[ChatMessage]:
        """Retrieve recent messages for a specific user (ordered newest → oldest)."""
        try:
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id),
                ScanIndexForward=False,  # Descending order (latest first)
                Limit=limit,
            )

            items = response.get("Items", [])
            messages = [ChatMessage.from_dict(item) for item in items]

            logger.info(f"Retrieved {len(messages)} messages for user {user_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to get user messages: {e}")
            return []

    def delete_user_messages(self, user_id: str) -> bool:
        """Delete all messages for a specific user."""
        try:
            response = self.table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("user_id").eq(user_id)
            )

            items = response.get("Items", [])

            with self.table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(
                        Key={
                            "user_id": item["user_id"],
                            "timestamp": item["timestamp"],
                        }
                    )

            logger.info(f"Deleted {len(items)} messages for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user messages: {e}")
            return False


# ----------------------------------------------------------------------
# SINGLETON FACTORY
# ----------------------------------------------------------------------

_dynamodb_client: DynamoDBClient | None = None


def get_dynamodb_client() -> DynamoDBClient:
    """Get or create a singleton instance of DynamoDBClient."""
    global _dynamodb_client

    if _dynamodb_client is None:
        _dynamodb_client = DynamoDBClient()

    return _dynamodb_client
