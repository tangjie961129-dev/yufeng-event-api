"""
问卷引擎模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func
from app.core.database import Base


class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    quiz_type = Column(String(50), default="custom")  # mbti / lgti / custom
    questions_count = Column(Integer, default=0)
    is_published = Column(Boolean, default=False)
    image_url = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(String(50), default="single_choice")  # single_choice / multi_choice / scale / input / textarea / picker / tags
    sort_order = Column(Integer, default=0)
    options = Column(JSON, default=list)  # [{label, value, score}]
    required = Column(Boolean, default=True)
    field_key = Column(String(80), default="")  # 小程序提交字段名，如 city/role_self
    placeholder = Column(String(300), default="")
    input_type = Column(String(30), default="text")  # text / number / idcard 等
    maxlength = Column(Integer, default=200)
    suffix = Column(String(30), default="")
    use_native_picker = Column(Boolean, default=False)
    help_text = Column(Text, default="")


class QuizResult(Base):
    __tablename__ = "quiz_results"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    min_score = Column(Float, default=0)
    max_score = Column(Float, default=100)
    title = Column(String(200), default="")
    description = Column(Text, default="")
    content = Column(Text, default="")
    image_url = Column(String(500), default="")
    result_type = Column(String(100), default="")
    traits = Column(JSON, default=list)
    scores = Column(JSON, default=dict)
    cta_title = Column(String(200), default="")
    cta_desc = Column(Text, default="")
    qrcode_url = Column(String(500), default="")
    share_text = Column(Text, default="")
    sort_order = Column(Integer, default=0)


class QuizSubmission(Base):
    __tablename__ = "quiz_submissions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    answers = Column(JSON, default=list)  # [{question_id, answer}]
    score = Column(Float, default=0.0)
    result_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
