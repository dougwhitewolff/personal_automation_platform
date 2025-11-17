"""
RAG (Retrieval-Augmented Generation) Service.

Handles semantic search and question answering using MongoDB Atlas Vector Search.
"""

from typing import List, Dict, Optional, Any
from pymongo.database import Database
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_mongodb import MongoDBAtlasVectorSearch
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
import os


class RAGService:
    """
    RAG service for answering questions using vector search over MongoDB records.
    """
    
    def __init__(
        self,
        db: Database,
        openai_api_key: str,
        collection_name: str = "rag_chunks",
        index_name: str = "vector_index",
        embedding_model: str = "text-embedding-3-small",
        llm_model: str = "gpt-5-nano",
        top_k: int = 5
    ):
        """
        Initialize RAG service.
        
        Args:
            db: MongoDB database instance
            openai_api_key: OpenAI API key
            collection_name: Name of the vector store collection
            index_name: Name of the vector search index
            embedding_model: OpenAI embedding model name
            llm_model: OpenAI LLM model name
            top_k: Number of top results to retrieve
        """
        self.db = db
        self.collection_name = collection_name
        self.index_name = index_name
        self.top_k = top_k
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=openai_api_key
        )
        
        # Initialize vector store
        self.vector_store = MongoDBAtlasVectorSearch(
            collection=db[collection_name],
            embedding=self.embeddings,
            index_name=index_name
        )
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=llm_model,
            openai_api_key=openai_api_key,
            temperature=0.7
        )
        
        # Create prompt template
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful personal automation assistant. You help users answer questions about their tracked data including nutrition, workouts, sleep, wellness, and health metrics.

Use the provided context from the user's records to answer their question accurately. If the context doesn't contain enough information to answer the question, say so clearly.

When providing numbers or statistics, be specific and cite the dates when relevant. Format your response in a natural, conversational way."""),
            ("human", """Context from user's records:
{context}

User's question: {question}

Answer the question based on the context provided. If the context doesn't have enough information, let the user know what information is missing.""")
        ])
        
        # Create RAG chain
        self.rag_chain = (
            {
                "context": self.vector_store.as_retriever(search_kwargs={"k": top_k}) | self._format_docs,
                "question": RunnablePassthrough()
            }
            | self.prompt_template
            | self.llm
            | StrOutputParser()
        )
    
    def _format_docs(self, docs: List[Any]) -> str:
        """
        Format retrieved documents into context string.
        
        Args:
            docs: List of retrieved document objects
            
        Returns:
            Formatted context string
        """
        formatted_parts = []
        for doc in docs:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}
            text = doc.page_content if hasattr(doc, 'page_content') else str(doc)
            
            # Add metadata context
            context_line = f"[{metadata.get('date', 'Unknown date')}] "
            if metadata.get('module'):
                context_line += f"{metadata.get('module').title()} - "
            if metadata.get('record_type'):
                context_line += f"{metadata.get('record_type')}: "
            
            context_line += text
            formatted_parts.append(context_line)
        
        return "\n\n".join(formatted_parts)
    
    def answer_query(self, query: str) -> str:
        """
        Answer a question using RAG.
        
        Args:
            query: User's question
            
        Returns:
            Answer string
        """
        try:
            answer = self.rag_chain.invoke(query)
            return answer
        except Exception as e:
            return f"I encountered an error while searching your records: {str(e)}"
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """
        Add documents to the vector store.
        
        Args:
            documents: List of document dicts with 'text' and 'metadata' keys
            
        Returns:
            List of document IDs
        """
        try:
            # Convert to LangChain document format
            from langchain_core.documents import Document
            langchain_docs = [
                Document(page_content=doc["text"], metadata=doc.get("metadata", {}))
                for doc in documents
            ]
            
            # Add to vector store
            ids = self.vector_store.add_documents(langchain_docs)
            return ids
        except Exception as e:
            print(f"⚠️  Error adding documents to vector store: {e}")
            return []
    
    def delete_documents_by_source_id(self, source_id: str, collection_name: str) -> bool:
        """
        Delete documents from vector store by source ID and collection.
        
        Args:
            source_id: Source document ID
            collection_name: Source collection name
            
        Returns:
            True if successful
        """
        try:
            collection = self.db[self.collection_name]
            result = collection.delete_many({
                "metadata.source_id": source_id,
                "metadata.source_collection": collection_name
            })
            return result.deleted_count > 0
        except Exception as e:
            print(f"⚠️  Error deleting documents from vector store: {e}")
            return False
    
    def vectorize_record(self, record: Dict, collection_name: str) -> bool:
        """
        Convenience method to vectorize a single record.
        
        Args:
            record: MongoDB document to vectorize
            collection_name: Name of the source collection
            
        Returns:
            True if successful
        """
        from utils.vectorization import chunk_record
        try:
            chunks = chunk_record(record, collection_name)
            if chunks:
                self.add_documents(chunks)
                return True
            return False
        except Exception as e:
            print(f"⚠️  Error vectorizing record: {e}")
            return False
    
    def ensure_index_exists(self):
        """
        Ensure the vector search index exists in MongoDB Atlas.
        This is a placeholder - actual index creation must be done via MongoDB Atlas UI or API.
        """
        print(f"ℹ️  Vector search index '{self.index_name}' should be created in MongoDB Atlas.")
        print(f"   Collection: {self.collection_name}")
        print(f"   Index configuration:")
        print(f"   - Fields: [{{'type': 'vector', 'path': 'embedding', 'numDimensions': 1536, 'similarity': 'cosine'}}]")
        print(f"   - Collection: {self.collection_name}")

