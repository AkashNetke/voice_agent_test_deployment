from langchain_openai import AzureChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from dotenv import load_dotenv
import os
from .travel_hands_client import TravelHandsClient
from typing import Tuple, Dict
import json


load_dotenv()

class Agent:
    def __init__(self) -> None:
        self.llm = AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            temperature=0.1, # temperature should be low for agent use
            max_tokens=10000
        )

        self.memory = ConversationBufferMemory(
            return_messages=True,
            ai_prefix="Assistant",
            human_prefix="User"
        )

        # we need an Agent with tool use here? rather than ConversationChain?
        # from langchain.agents import AgentType, initialize_agent
        self.conversation = ConversationChain(
            llm=self.llm,
            memory=self.memory,
            verbose=True
        )

        # we should use langchain tools annotation todo
        self.travel_hands_client = TravelHandsClient()

    # do not know why this is required todo
    def _classify_query_intent(self, query: str) -> Tuple[str, Dict]:
        query_lower = query.lower()
        # First check for Travel Hands specific patterns
        if "active journey" in query_lower and "user" in query_lower:
            # Extract user ID using regex
            import re
            user_id_match = re.search(r'user\s*(\d+)', query_lower)
            user_id = int(user_id_match.group(1)) if user_id_match else None
            return ("TRAVEL_HANDS", {"specific_intent": "active_journey", "parameters": {"user_id": user_id}})

        elif "get volunteers" in query_lower:
            return ("TRAVEL_HANDS", {"specific_intent": "get_volunteers", "parameters": {}})

        # If no pattern match, use LLM classification
        # todo this Prompt should go into agent initialization
        prompt = PromptTemplate(
            input_variables=["query"],
            template="""
            Determine whether the following query is asking for:
            1. Real-time data about users, tasks, or projects (API)
            2. Information about features, how-to guides, or FAQs (DOCS)

            Query: {query}

            If it's an API query, also identify what specific data is being requested and any parameters needed.
            If it's a DOCS query, identify what specific information is being requested.

            Output your answer in the following JSON format:
            {{
                "type": "API" or "DOCS",
                "specific_intent": "<specific intent like 'active_users', 'tasks_for_user', 'upcoming_features', 'how_to_create_action', etc.>",
                "parameters": {{<any parameters needed for the API call, such as user_id, task_id, etc.>}}
            }}
            """
        )

        response = self.llm.invoke(prompt.format(query=query))
        self.logger.info(f"LLM classification response: {response.content}")

    def _handle_travel_hands_query(self, specific_intent: str, parameters: Dict) -> str:
        """
        Handle Travel Hands API queries.

        Args:
            specific_intent: Specific intent of the query
            parameters: Parameters for the query

        Returns:
            Generated response for the user
        """
        try:
            if specific_intent == "active_journey":
                user_id = parameters.get("user_id")
                if not user_id:
                    return "Please provide a valid user ID to check active journey."

                response = self.travel_hands_client.get_active_journey(user_id)

                # Format the response nicely
                prompt = f"""
                Based on the active journey data, provide a helpful response.

                Journey data: {json.dumps(response, indent=2)}

                In your response:
                1. Mention key journey details (pickup, destination, status)
                2. Include any relevant timestamps
                3. Present the information in a conversational way
                4. Don't include any JSON formatting in your response
                """
                return self.llm.invoke(prompt).content

            elif specific_intent == "get_volunteers":
                # You can add more parameters here based on the swagger spec
                request_data = {}
                response = self.travel_hands_client.get_volunteers(request_data)

                prompt = f"""
                Based on the volunteers data, provide a helpful response.

                Volunteers data: {json.dumps(response, indent=2)}

                In your response:
                1. Mention how many volunteers are available
                2. Include key information about volunteers
                3. Present the information in a conversational way
                4. Don't include any JSON formatting in your response
                """
                return self.llm.invoke(prompt).content

        except Exception as e:
            error_message = str(e)
            self.logger.error(f"Error handling Travel Hands query: {error_message}")
            return f"I encountered an error while processing your request: {error_message}"

    def process_query(self, query: str) -> str:
        """
        Process a user query and return a response.

        Args:
            query: User's query

        Returns:
            Agent's response
        """
        self.logger.info(f"Processing query: {query}")

        # Classify the query intent
        intent_type, intent_details = self._classify_query_intent(query)
        self.logger.info(f"Query classified as: {intent_type} with details: {intent_details}")

        # Handle based on intent type
        if intent_type == "API":
            self.logger.info(f"Handling as API query: {intent_details['specific_intent']}")
            response = self._handle_api_query(
                specific_intent=intent_details["specific_intent"],
                parameters=intent_details["parameters"]
            )
        elif intent_type == "TRAVEL_HANDS":
            self.logger.info(f"Handling as TRAVEL_HANDS query: {intent_details['specific_intent']}")
            response = self._handle_travel_hands_query(
                specific_intent=intent_details["specific_intent"],
                parameters=intent_details["parameters"]
            )
        else:  # intent_type == "DOCS"
            self.logger.info(f"Handling as DOCS query: {intent_details['specific_intent']}")
            response = self._handle_doc_query(
                query=query,
                specific_intent=intent_details["specific_intent"]
            )

        # Update conversation memory
        self.memory.save_context({"input": query}, {"output": response})
        self.logger.info(f"Response generated: {response[:100]}..." if len(response) > 100 else f"Response generated: {response}")

        return response
