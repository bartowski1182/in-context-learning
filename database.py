from sqlalchemy import create_engine, Column, Integer, String, JSON, Float, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import chromadb
from typing import List, Dict, Tuple
from config import Config
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

Base = declarative_base()


class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True)
    question_id = Column(String)
    answer = Column(String)


class Result(Base):
    __tablename__ = "results"
    id = Column(Integer, primary_key=True)
    question = Column(String)
    context_qa = Column(JSON)
    with_context_answer = Column(String)
    without_context_answer = Column(String)
    with_context_score = Column(Float)
    without_context_score = Column(Float)
    with_context_better = Column(Boolean)


class DatabaseManager:
    def __init__(self, config: Config):
        self.config = config
        model_kwargs = {"device": "cuda"}
        encode_kwargs = {"normalize_embeddings": True}
        self.embeddings_model = HuggingFaceBgeEmbeddings(
            model_name=config.embedding_model,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )
        self.connection = Chroma(
            persist_directory=config.vector_db_path,
            embedding_function=self.embeddings_model,
        )
        self.results_engine = create_engine(config.results_db_path)
        Base.metadata.create_all(self.results_engine)

    def store_qa_pairs(self, qa_pairs: List[dict]):
        # Store question in vector DB
        docs = []

        for qa_pair in qa_pairs:
            metadata = {"question_id": qa_pair["id"], "answer": qa_pair["answer"]}
            docs.append(Document(page_content=qa_pair["question"], metadata=metadata))

        self.connection.add_documents(
            documents=docs,
        )

    def find_similar_question(self, question: str) -> Tuple[str, str]:
        results = self.connection.similarity_search(question, k=1)

        return results[0].page_content, results[0].metadata["answer"]

    def store_result(self, result: Dict):
        Session = sessionmaker(bind=self.results_engine)
        with Session() as session:
            result_record = Result(**result)
            session.add(result_record)
            session.commit()
