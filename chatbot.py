# chatbot.py

import os
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.vectorstores import Qdrant
from langchain_ollama import ChatOllama
from qdrant_client import QdrantClient
from langchain_core.prompts import PromptTemplate
import streamlit as st

class ChatbotManager:
    def __init__(
        self,
        model_name: str = "BAAI/bge-small-en",
        device: str = "cpu",
        encode_kwargs: dict = {"normalize_embeddings": True},
        llm_model: str = "llama3.2:latest",
        llm_temperature: float = 0.7,
        qdrant_path: str = "local_qdrant",
        collection_name: str = "vector_db",
    ):
        """
        Initializes the ChatbotManager with embedding models, LLM, and vector store.

        Args:
            model_name (str): The HuggingFace model name for embeddings.
            device (str): The device to run the model on ('cpu' or 'cuda').
            encode_kwargs (dict): Additional keyword arguments for encoding.
            llm_model (str): The local LLM model name for ChatOllama.
            llm_temperature (float): Temperature setting for the LLM.
            qdrant_url (str): The URL for the Qdrant instance.
            collection_name (str): The name of the Qdrant collection.
        """
        self.model_name = model_name
        self.device = device
        self.encode_kwargs = encode_kwargs
        self.llm_model = llm_model
        self.llm_temperature = llm_temperature
        self.qdrant_path = qdrant_path
        self.collection_name = collection_name

        # Initialize Embeddings
        self.embeddings = HuggingFaceBgeEmbeddings(
            model_name=self.model_name,
            model_kwargs={"device": self.device},
            encode_kwargs=self.encode_kwargs,
        )

        # Initialize Local LLM
        self.llm = ChatOllama(
            model=self.llm_model,
            temperature=self.llm_temperature,
            # Add other parameters if needed
        )

        # Define the prompt template — strict grounding
        self.prompt_template = """You are a document analysis assistant. You MUST answer ONLY using the information provided in the Context below. 

RULES:
- ONLY use facts explicitly stated in the Context.
- If the answer is NOT in the Context, say "I couldn't find that information in the uploaded document."
- Do NOT make up, infer, or assume information that is not directly stated.
- Do NOT use your own general knowledge. Only the Context matters.
- Quote or reference specific parts of the Context when possible.

Context:
{context}

Question: {question}

Answer (strictly from the context above):"""

        # Initialize Qdrant client
        self.client = QdrantClient(
            path=self.qdrant_path, prefer_grpc=False
        )

        # Initialize the Qdrant vector store
        self.db = Qdrant(
            client=self.client,
            embeddings=self.embeddings,
            collection_name=self.collection_name
        )

        # Initialize the prompt
        self.prompt = PromptTemplate(
            template=self.prompt_template,
            input_variables=['context', 'question']
        )

    def get_response(self, query: str) -> str:
        """
        Processes the user's query and returns the chatbot's response.
        """
        try:
            context = self._get_context(query)
            formatted_prompt = self.prompt.format(context=context, question=query)
            response = self.llm.invoke(formatted_prompt)
            return response.content
        except Exception as e:
            return f"⚠️ Sorry, I couldn't process your request: {e}"

    def stream_response(self, query: str):
        """
        Streams the response token by token (generator).
        """
        try:
            context = self._get_context(query)
            formatted_prompt = self.prompt.format(context=context, question=query)
            for chunk in self.llm.stream(formatted_prompt):
                if hasattr(chunk, 'content') and chunk.content:
                    yield chunk.content
        except Exception as e:
            yield f"⚠️ Error: {e}"

    def _get_context(self, query: str) -> str:
        """
        Retrieves relevant context from the vector DB.
        """
        import numpy as np

        query_embedding = self.embeddings.embed_query(query)

        scroll_result = self.client.scroll(
            collection_name=self.collection_name,
            limit=100,
            with_payload=True,
            with_vectors=True
        )

        similarities = []
        for point in scroll_result[0]:
            if hasattr(point, 'vector') and point.vector:
                doc_vector = np.array(point.vector)
                query_vec = np.array(query_embedding)
                similarity = np.dot(doc_vector, query_vec) / (
                    np.linalg.norm(doc_vector) * np.linalg.norm(query_vec)
                )
                similarities.append((similarity, point.payload.get('page_content', '')))

        similarities.sort(key=lambda x: x[0], reverse=True)
        top_chunks = similarities[:3]

        if top_chunks:
            return "\n\n".join([chunk[1] for chunk in top_chunks])
        return "No relevant information found in the document."

