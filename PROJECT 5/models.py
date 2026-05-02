from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

class Organisation(Base):
    __tablename__ = "organisations"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    org_id = Column(Integer, ForeignKey("organisations.id"))

class Form(Base):
    __tablename__ = "forms"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    # FAULTY: Missing org_id. Currently, any form belongs to "everyone".
    content = Column(Text)