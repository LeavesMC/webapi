from sqlalchemy import Column, VARCHAR, Integer, Boolean, DateTime, CHAR

from sqlalchemy.orm import declarative_base

Base = declarative_base()

PROJECTS = [
    {
        "project_id": "leaves",
        "project_name": "leaves",
        "version_groups": ["1.20"],
        "versions": ["1.20.1"],
    }
]


class Project(Base):
    __tablename__ = "project_info"

    project_id = Column(VARCHAR(255), primary_key=True)
    version = Column(VARCHAR(255), primary_key=True)
    build = Column(Integer, primary_key=True)
    project_name = Column(VARCHAR(255))
    version_group = Column(VARCHAR(255))
    channel = Column(VARCHAR(255))
    promoted = Column(Boolean)
    time = Column(DateTime)


class File(Base):
    __tablename__ = "file_info"

    sha256 = Column(CHAR(64), primary_key=True)
    type = Column(VARCHAR(255))
    name = Column(VARCHAR(255))
    build = Column(Integer)
    version = Column(VARCHAR(255))
    version_group = Column(VARCHAR(255))
    url = Column(VARCHAR(255))
    project_id = Column(VARCHAR(255))


class Commit(Base):
    __tablename__ = "commit_info"

    hash = Column(CHAR(40), primary_key=True)
    message = Column(VARCHAR(2048))
    summary = Column(VARCHAR(2048))
    build = Column(Integer)
    version = Column(VARCHAR(255))
    version_group = Column(VARCHAR(255))
    project_id = Column(VARCHAR(255))
