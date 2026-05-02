from sqlalchemy import Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

# Many-to-Many Link for Tags
doc_tags = Table(
    "doc_tags",
    Base.metadata,
    Column("document_id", ForeignKey("documents.id")),
    Column("tag_id", ForeignKey("tags.id")),
)

class Author(Base):
    __tablename__ = "authors"
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(String)
    author_id = Column(Integer, ForeignKey("authors.id"))
    
    author = relationship("Author")
    tags = relationship("Tag", secondary=doc_tags)