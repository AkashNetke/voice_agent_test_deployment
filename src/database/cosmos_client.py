import os
import logging
from typing import List, Optional
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey
from dotenv import load_dotenv
from .models import ChatMessage

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CosmosDBClient:
    """Client for interacting with Azure Cosmos DB for chat history."""

    def __init__(self):
        """Initialize the Cosmos DB client."""
        self.endpoint = os.getenv("COSMOS_DB_ENDPOINT")
        self.key = os.getenv("COSMOS_DB_KEY")
        self.database_name = os.getenv("COSMOS_DB_DATABASE")
        self.container_name = os.getenv("COSMOS_CHAT_MESSAGE_CONTAINER")

        if not self.endpoint or not self.key:
            raise ValueError("COSMOS_DB_ENDPOINT and COSMOS_DB_KEY must be set in environment variables")

        self.client = CosmosClient(self.endpoint, self.key)
        self.database = None
        self.messages_container = None

        self._initialize_database()

    def _initialize_database(self):
        """Initialize database and containers."""
        try:
            # Get or create database
            self.database = self.client.get_database_client(self.database_name)
            try:
                self.database.read()
                logger.info(f"Connected to existing database: {self.database_name}")
            except Exception:
                self.database = self.client.create_database(self.database_name)
                logger.info(f"Created new database: {self.database_name}")

            try:
                # Check if container exists first
                try:
                    self.messages_container = self.database.get_container_client(self.container_name)
                    logger.info("Using existing chat messages container")
                except:
                    # Container doesn't exist, create it
                    self.messages_container = self.database.create_container(
                        id=self.container_name,
                        partition_key=PartitionKey(path="/user_id"),  # Partition by user_id
                        offer_throughput=400,
                        default_ttl=86400  # 24 hours in seconds
                    )
                    logger.info("Messages container created with throughput and 24h TTL")
            except Exception as e:
                if "serverless" in str(e).lower() or "offer throughput" in str(e).lower():
                    logger.info("Serverless account detected, creating container without throughput")
                    try:
                        self.messages_container = self.database.get_container_client(self.container_name)
                        logger.info("Using existing chat messages container")
                    except:
                        self.messages_container = self.database.create_container(
                            id=self.container_name,
                            partition_key=PartitionKey(path="/user_id"),
                            default_ttl=86400  # 24 hours in seconds
                        )
                        logger.info("Messages container created (serverless) with 24h TTL")
                else:
                    raise

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def save_message(self, message: ChatMessage) -> bool:
        """Save a message to Cosmos DB."""
        try:
            message_data = message.to_dict()
            # The partition key is automatically handled by the container configuration
            self.messages_container.create_item(message_data)
            logger.info(f"Message saved for user {message.user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return False

    def get_user_messages(self, user_id: str, limit: int = 100) -> List[ChatMessage]:
        """Get all messages for a specific user."""
        try:
            query = "SELECT * FROM c WHERE c.user_id = @user_id ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
            parameters = [
                {"name": "@user_id", "value": user_id},
                {"name": "@limit", "value": limit}
            ]

            # Use cross-partition query since the container might not be partitioned by user_id
            items = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))

            messages = [ChatMessage.from_dict(item) for item in items]
            logger.info(f"Retrieved {len(messages)} messages for user {user_id}")
            return messages

        except Exception as e:
            logger.error(f"Failed to get user messages: {e}")
            return []

    def delete_user_messages(self, user_id: str) -> bool:
        """Delete all messages for a specific user."""
        try:
            query = "SELECT c.id FROM c WHERE c.user_id = @user_id"
            parameters = [{"name": "@user_id", "value": user_id}]

            items = list(self.messages_container.query_items(
                query=query,
                parameters=parameters,
                partition_key=user_id
            ))

            for item in items:
                self.messages_container.delete_item(
                    item=item["id"],
                    partition_key=user_id
                )

            logger.info(f"Deleted all messages for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete user messages: {e}")
            return False

# Singleton instance
_cosmos_client = None

def get_cosmos_client() -> CosmosDBClient:
    """Get or create a singleton instance of CosmosDBClient."""
    global _cosmos_client
    if _cosmos_client is None:
        _cosmos_client = CosmosDBClient()
    return _cosmos_client
