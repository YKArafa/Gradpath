from datetime import datetime
from typing import Any, Optional
from sqlalchemy import (
    String,
    Text,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    CheckConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, synonym


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class Degree(Base):
    __tablename__ = "degree"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    courses: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list
    )

    # Relationships
    majors: Mapped[list["Major"]] = relationship("Major", back_populates="degree", cascade="all, delete-orphan")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="degree")

    # Synonyms for flexible access
    required_courses = synonym("courses")

    def __repr__(self) -> str:
        return f"<Degree(id={self.id}, name='{self.name}', courses={self.courses})>"


class Major(Base):
    __tablename__ = "major"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    degree_id: Mapped[int] = mapped_column(Integer, ForeignKey("degree.id", ondelete="CASCADE"), nullable=False)
    required_courses: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list
    )

    # Relationships
    degree: Mapped["Degree"] = relationship("Degree", back_populates="majors")
    students: Mapped[list["Student"]] = relationship("Student", back_populates="major")

    def __repr__(self) -> str:
        return f"<Major(id={self.id}, name='{self.name}', degree_id={self.degree_id})>"


class Advisor(Base):
    __tablename__ = "advisor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    students: Mapped[list["Student"]] = relationship("Student", back_populates="advisor")

    def __repr__(self) -> str:
        return f"<Advisor(id={self.id}, name='{self.name}', email='{self.email}', institution='{self.institution}')>"


class Course(Base):
    __tablename__ = "course"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    credit_hours: Mapped[float] = mapped_column(Numeric(4, 2), nullable=False)
    difficulty_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'medium'"),
        default="medium",
    )
    prerequisites: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list
    )

    # Synonyms for flexible access
    difficulty = synonym("difficulty_level")

    __table_args__ = (
        CheckConstraint(
            "difficulty_level IN ('low', 'medium', 'hard')",
            name="check_course_difficulty_level",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Course(id={self.id}, code='{self.code}', title='{self.title}', "
            f"credit_hours={self.credit_hours}, difficulty_level='{self.difficulty_level}')>"
        )


class Student(Base):
    __tablename__ = "student"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    advisor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("advisor.id", ondelete="SET NULL"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    institution: Mapped[str] = mapped_column(String(255), nullable=False)
    time_of_enrollment: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    degree_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("degree.id", ondelete="RESTRICT"),
        nullable=False
    )
    major_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("major.id", ondelete="SET NULL"),
        nullable=True
    )
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
        default=dict
    )
    gpa: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    advisor: Mapped[Optional["Advisor"]] = relationship("Advisor", back_populates="students")
    degree: Mapped["Degree"] = relationship("Degree", back_populates="students")
    major: Mapped[Optional["Major"]] = relationship("Major", back_populates="students")
    transcripts: Mapped[list["Transcript"]] = relationship(
        "Transcript",
        back_populates="student",
        cascade="all, delete-orphan"
    )

    # GPA alias / synonym
    GPA = synonym("gpa")

    def __repr__(self) -> str:
        return f"<Student(id={self.id}, name='{self.name}', email='{self.email}', gpa={self.gpa})>"


class Transcript(Base):
    __tablename__ = "transcript"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("student.id", ondelete="CASCADE"),
        nullable=False
    )
    # Array containing the semester (string) and a map of course_id and the numeric grade value
    # Example format:
    # [
    #   {
    #     "semester": "Fall 2024",
    #     "courses": {"1": 3.7, "2": 4.0}
    #   }
    # ]
    semesters: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
        default=list
    )

    # Relationships
    student: Mapped["Student"] = relationship("Student", back_populates="transcripts")

    # Synonyms for flexible access
    records = synonym("semesters")
    grades = synonym("semesters")

    def __repr__(self) -> str:
        return f"<Transcript(id={self.id}, student_id={self.student_id}, semesters_count={len(self.semesters)})>"
