"""
RAG (Retrieval-Augmented Generation) Service.

Handles semantic search and question answering using Pinecone Vector Database.
"""

# Windows compatibility: ensure readline is available before Pinecone imports it
import sys
if sys.platform == "win32":
    try:
        import readline
    except ImportError:
        try:
            import pyreadline3 as readline
            sys.modules['readline'] = readline
        except ImportError:
            pass  # readline is optional for Pinecone functionality

from typing import List, Dict, Optional, Any
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from pinecone import Pinecone, ServerlessSpec
import os


class RAGService:
    """
    RAG service for answering questions using vector search over Pinecone records.
    """
    
    def __init__(
        self,
        pinecone_api_key: str,
        openai_api_key: str,
        index_name: str = "rag-chunks",
        namespace: str = "default",
        embedding_model: str = "text-embedding-3-small",
        llm_model: str = "gpt-5-nano",
        top_k: int = 5,
        dimension: int = 1536
    ):
        """
        Initialize RAG service.
        
        Args:
            pinecone_api_key: Pinecone API key
            openai_api_key: OpenAI API key
            index_name: Name of the Pinecone index
            namespace: Pinecone namespace (default: "default")
            embedding_model: OpenAI embedding model name
            llm_model: OpenAI LLM model name
            top_k: Number of top results to retrieve
            dimension: Vector dimension (1536 for text-embedding-3-small)
        """
        self.index_name = index_name
        self.namespace = namespace
        self.top_k = top_k
        self.dimension = dimension
        
        # Initialize Pinecone client
        self.pinecone_client = Pinecone(api_key=pinecone_api_key)
        
        # Ensure index exists
        self._ensure_index_exists(dimension)
        
        # Initialize embeddings
        self.embeddings = OpenAIEmbeddings(
            model=embedding_model,
            openai_api_key=openai_api_key
        )
        
        # Initialize vector store
        self.vector_store = PineconeVectorStore(
            index_name=index_name,
            embedding=self.embeddings,
            namespace=namespace,
            pinecone_api_key=pinecone_api_key
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
            try:
                print(f"⚠️  Error adding documents to vector store: {e}")
            except UnicodeEncodeError:
                print(f"[WARN] Error adding documents to vector store: {e}")
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
            index = self.pinecone_client.Index(self.index_name)
            
            # Try to delete using filter (supported in newer Pinecone versions)
            try:
                index.delete(
                    filter={
                        "source_id": {"$eq": source_id},
                        "source_collection": {"$eq": collection_name}
                    },
                    namespace=self.namespace
                )
                return True
            except Exception:
                # Fallback: Query first, then delete by IDs
                # Use a small random vector for the query (Pinecone requires a vector)
                import random
                query_vector = [random.random() * 0.001 for _ in range(self.dimension)]
                
                query_results = index.query(
                    vector=query_vector,
                    top_k=10000,  # Large number to get all matches
                    include_metadata=True,
                    filter={
                        "source_id": {"$eq": source_id},
                        "source_collection": {"$eq": collection_name}
                    },
                    namespace=self.namespace
                )
                
                if query_results.matches:
                    ids_to_delete = [match.id for match in query_results.matches]
                    if ids_to_delete:
                        index.delete(ids=ids_to_delete, namespace=self.namespace)
                        return True
                return False
        except Exception as e:
            try:
                print(f"⚠️  Error deleting documents from vector store: {e}")
            except UnicodeEncodeError:
                print(f"[WARN] Error deleting documents from vector store: {e}")
            return False
    
    def vectorize_record(self, record: Dict, collection_name: str) -> bool:
        """
        Convenience method to vectorize a single record.
        
        Args:
            record: Document to vectorize (dict with data)
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
            try:
                print(f"⚠️  Error vectorizing record: {e}")
            except UnicodeEncodeError:
                print(f"[WARN] Error vectorizing record: {e}")
            return False
    
    def _ensure_index_exists(self, dimension: int = 1536):
        """
        Ensure the Pinecone index exists, create it if it doesn't.
        
        Args:
            dimension: Vector dimension (default: 1536 for text-embedding-3-small)
        """
        def safe_print(text):
            """Safe print that handles Windows encoding issues."""
            try:
                print(text)
            except UnicodeEncodeError:
                text = text.replace("✅", "[OK]")
                text = text.replace("❌", "[ERROR]")
                text = text.replace("⚠️", "[WARN]")
                text = text.replace("📦", "[INFO]")
                text = text.replace("ℹ️", "[INFO]")
                print(text)
        
        try:
            existing_indexes = [index.name for index in self.pinecone_client.list_indexes()]
            
            if self.index_name not in existing_indexes:
                safe_print(f"📦 Creating Pinecone index '{self.index_name}'...")
                self.pinecone_client.create_index(
                    name=self.index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"  # Default region, can be configured
                    )
                )
                safe_print(f"✅ Pinecone index '{self.index_name}' created successfully")
            else:
                safe_print(f"✅ Pinecone index '{self.index_name}' already exists")
        except Exception as e:
            safe_print(f"⚠️  Error ensuring index exists: {e}")
            raise

