"""
问卷引擎管理后台 API
"""
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.admin import AdminUser
from app.models.quiz import Quiz, QuizQuestion, QuizResult, QuizSubmission

router = APIRouter(prefix="/api/admin", tags=["后台问卷管理"])


# ====== Schemas ======

class QuizCreate(BaseModel):
    title: str
    description: str = ""
    quiz_type: str = "custom"
    questions_count: int = 0
    is_published: bool = False
    image_url: str = ""


class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    quiz_type: Optional[str] = None
    questions_count: Optional[int] = None
    is_published: Optional[bool] = None
    image_url: Optional[str] = None


class OptionItem(BaseModel):
    label: str
    value: str
    score: float = 0.0


class QuestionCreate(BaseModel):
    question_text: str
    question_type: str = "single_choice"
    sort_order: int = 0
    options: List[OptionItem] = []
    required: bool = True
    field_key: str = ""
    placeholder: str = ""
    input_type: str = "text"
    maxlength: int = 200
    suffix: str = ""
    use_native_picker: bool = False
    help_text: str = ""


class QuestionUpdate(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    sort_order: Optional[int] = None
    options: Optional[List[OptionItem]] = None
    required: Optional[bool] = None
    field_key: Optional[str] = None
    placeholder: Optional[str] = None
    input_type: Optional[str] = None
    maxlength: Optional[int] = None
    suffix: Optional[str] = None
    use_native_picker: Optional[bool] = None
    help_text: Optional[str] = None


class ResultCreate(BaseModel):
    min_score: float = 0
    max_score: float = 100
    title: str = ""
    description: str = ""
    content: str = ""
    image_url: str = ""
    result_type: str = ""
    traits: list = []
    scores: dict = {}
    cta_title: str = ""
    cta_desc: str = ""
    qrcode_url: str = ""
    share_text: str = ""
    sort_order: int = 0


class ResultUpdate(BaseModel):
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    image_url: Optional[str] = None
    result_type: Optional[str] = None
    traits: Optional[list] = None
    scores: Optional[dict] = None
    cta_title: Optional[str] = None
    cta_desc: Optional[str] = None
    qrcode_url: Optional[str] = None
    share_text: Optional[str] = None
    sort_order: Optional[int] = None




def _serialize_question(q: QuizQuestion) -> dict:
    return {
        "id": q.id, "quiz_id": q.quiz_id, "question_text": q.question_text, "question_type": q.question_type,
        "sort_order": q.sort_order, "options": q.options or [], "required": q.required,
        "field_key": q.field_key or "", "placeholder": q.placeholder or "",
        "input_type": q.input_type or "text", "maxlength": q.maxlength or 200,
        "suffix": q.suffix or "", "use_native_picker": bool(q.use_native_picker),
        "help_text": q.help_text or "",
    }

def _serialize_result(r: QuizResult) -> dict:
    return {
        "id": r.id, "quiz_id": r.quiz_id, "min_score": r.min_score, "max_score": r.max_score,
        "title": r.title, "description": r.description, "content": r.content, "image_url": r.image_url,
        "result_type": r.result_type or "", "traits": r.traits or [], "scores": r.scores or {},
        "cta_title": r.cta_title or "", "cta_desc": r.cta_desc or "",
        "qrcode_url": r.qrcode_url or "", "share_text": r.share_text or "", "sort_order": r.sort_order or 0,
    }

# ====== Quiz CRUD ======

@router.get("/quizzes")
def list_all_quizzes(
    page: int = 1,
    page_size: int = 20,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理列表（全部问卷）"""
    query = db.query(Quiz)
    total = query.count()
    quizzes = query.order_by(Quiz.id.desc()) \
                   .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for q in quizzes:
        items.append({
            "id": q.id,
            "title": q.title,
            "description": q.description,
            "quiz_type": q.quiz_type,
            "questions_count": q.questions_count,
            "is_published": q.is_published,
            "image_url": q.image_url,
            "created_at": q.created_at,
            "updated_at": q.updated_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/quizzes")
def create_quiz(
    req: QuizCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建问卷"""
    quiz = Quiz(**req.model_dump())
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {
        "id": quiz.id,
        "message": "创建成功",
    }


@router.put("/quizzes/{quiz_id}")
def update_quiz(
    quiz_id: int,
    req: QuizUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新问卷"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(quiz, key, value)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/quizzes/{quiz_id}")
def delete_quiz(
    quiz_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除问卷（级联删除题目和结果）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    # 级联删除
    db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz_id).delete()
    db.query(QuizResult).filter(QuizResult.quiz_id == quiz_id).delete()
    db.delete(quiz)
    db.commit()
    return {"message": "删除成功"}


@router.get("/quizzes/{quiz_id}")
def get_quiz_detail(
    quiz_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """问卷详情（含题目和结果区间）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    questions = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_id == quiz_id
    ).order_by(QuizQuestion.sort_order.asc(), QuizQuestion.id.asc()).all()

    results = db.query(QuizResult).filter(
        QuizResult.quiz_id == quiz_id
    ).order_by(QuizResult.sort_order.asc(), QuizResult.min_score.asc()).all()

    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "quiz_type": quiz.quiz_type,
        "questions_count": quiz.questions_count,
        "is_published": quiz.is_published,
        "image_url": quiz.image_url,
        "created_at": quiz.created_at,
        "updated_at": quiz.updated_at,
        "questions": [
_serialize_question(q)
            for q in questions
        ],
        "results": [
_serialize_result(r)
            for r in results
        ],
    }


# ====== Questions CRUD ======

@router.post("/quizzes/{quiz_id}/questions")
def add_question(
    quiz_id: int,
    req: QuestionCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """添加题目"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    question = QuizQuestion(
        quiz_id=quiz_id,
        question_text=req.question_text,
        question_type=req.question_type,
        sort_order=req.sort_order,
        options=[o.model_dump() for o in req.options],
        required=req.required,
        field_key=req.field_key,
        placeholder=req.placeholder,
        input_type=req.input_type,
        maxlength=req.maxlength,
        suffix=req.suffix,
        use_native_picker=req.use_native_picker,
        help_text=req.help_text,
    )
    db.add(question)

    # 更新问卷题目数量
    quiz.questions_count = (quiz.questions_count or 0) + 1
    db.commit()
    db.refresh(question)

    return {
        "id": question.id,
        "message": "添加成功",
    }


@router.get("/quizzes/{quiz_id}/questions")
def list_questions(
    quiz_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """列出问卷题目（前端桥接接口）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    questions = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_id == quiz_id
    ).order_by(QuizQuestion.sort_order.asc(), QuizQuestion.id.asc()).all()

    return {
        "items": [_serialize_question(q) for q in questions],
        "total": len(questions),
    }


@router.put("/quizzes/{quiz_id}/questions/{question_id}")
def update_question_bridge(
    quiz_id: int,
    question_id: int,
    req: QuestionUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新题目（前端桥接接口）"""
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id, QuizQuestion.quiz_id == quiz_id).first()
    if not question:
        raise HTTPException(404, "题目不存在")

    update_data = req.model_dump(exclude_none=True)
    if "options" in update_data and update_data["options"] is not None:
        update_data["options"] = [
            o.model_dump() if hasattr(o, "model_dump") else o
            for o in update_data["options"]
        ]

    for key, value in update_data.items():
        setattr(question, key, value)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/quizzes/{quiz_id}/questions/{question_id}")
def delete_question_bridge(
    quiz_id: int,
    question_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除题目（前端桥接接口）"""
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id, QuizQuestion.quiz_id == quiz_id).first()
    if not question:
        raise HTTPException(404, "题目不存在")

    # 更新问卷题目数量
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if quiz:
        quiz.questions_count = max(0, (quiz.questions_count or 1) - 1)

    db.delete(question)
    db.commit()
    return {"message": "删除成功"}


# 保留旧版路径兼容性
@router.put("/questions/{question_id}")
def update_question(
    question_id: int,
    req: QuestionUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新题目"""
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question:
        raise HTTPException(404, "题目不存在")

    update_data = req.model_dump(exclude_none=True)
    if "options" in update_data and update_data["options"] is not None:
        update_data["options"] = [
            o.model_dump() if hasattr(o, "model_dump") else o
            for o in update_data["options"]
        ]

    for key, value in update_data.items():
        setattr(question, key, value)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除题目"""
    question = db.query(QuizQuestion).filter(QuizQuestion.id == question_id).first()
    if not question:
        raise HTTPException(404, "题目不存在")

    # 更新问卷题目数量
    quiz = db.query(Quiz).filter(Quiz.id == question.quiz_id).first()
    if quiz:
        quiz.questions_count = max(0, (quiz.questions_count or 1) - 1)

    db.delete(question)
    db.commit()
    return {"message": "删除成功"}


# ====== Range Schemas (前端桥接) ======

class RangeCreate(BaseModel):
    label: str = ""
    min_score: float = 0
    max_score: float = 100
    description: str = ""
    result_image: str = ""


class RangeUpdate(BaseModel):
    label: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    description: Optional[str] = None
    result_image: Optional[str] = None


# ====== Results CRUD ======



@router.post("/quizzes/{quiz_id}/results")
def add_result(
    quiz_id: int,
    req: ResultCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """添加结果区间"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    result = QuizResult(
        quiz_id=quiz_id,
        min_score=req.min_score,
        max_score=req.max_score,
        title=req.title,
        description=req.description,
        content=req.content,
        image_url=req.image_url,
        result_type=req.result_type,
        traits=req.traits,
        scores=req.scores,
        cta_title=req.cta_title,
        cta_desc=req.cta_desc,
        qrcode_url=req.qrcode_url,
        share_text=req.share_text,
        sort_order=req.sort_order,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    return {
        "id": result.id,
        "message": "添加成功",
    }


@router.put("/results/{result_id}")
def update_result(
    result_id: int,
    req: ResultUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新结果区间"""
    result = db.query(QuizResult).filter(QuizResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "结果区间不存在")

    update_data = req.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(result, key, value)

    db.commit()
    return {"message": "更新成功"}


@router.delete("/results/{result_id}")
def delete_result(
    result_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除结果区间"""
    result = db.query(QuizResult).filter(QuizResult.id == result_id).first()
    if not result:
        raise HTTPException(404, "结果区间不存在")

    db.delete(result)
    db.commit()
    return {"message": "删除成功"}


# ====== Ranges Bridge (前端桥接) ======

@router.get("/quizzes/{quiz_id}/ranges")
def list_ranges(
    quiz_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """列出结果区间（前端桥接）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    results = db.query(QuizResult).filter(
        QuizResult.quiz_id == quiz_id
    ).order_by(QuizResult.sort_order.asc(), QuizResult.min_score.asc()).all()

    return {
        "items": [_serialize_result(r) for r in results],
        "total": len(results),
    }


@router.post("/quizzes/{quiz_id}/ranges")
def create_range(
    quiz_id: int,
    req: RangeCreate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """创建结果区间（前端桥接，字段映射 label→title, result_image→image_url）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    result = QuizResult(
        quiz_id=quiz_id,
        min_score=req.min_score,
        max_score=req.max_score,
        title=req.label,
        description=req.description,
        content="",
        image_url=req.result_image or "",
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return {"id": result.id, "message": "添加成功"}


@router.put("/quizzes/{quiz_id}/ranges/{range_id}")
def update_range(
    quiz_id: int,
    range_id: int,
    req: RangeUpdate,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """更新结果区间（前端桥接，字段映射 label→title, result_image→image_url）"""
    result = db.query(QuizResult).filter(
        QuizResult.id == range_id,
        QuizResult.quiz_id == quiz_id,
    ).first()
    if not result:
        raise HTTPException(404, "结果区间不存在")

    if req.label is not None:
        result.title = req.label
    if req.min_score is not None:
        result.min_score = req.min_score
    if req.max_score is not None:
        result.max_score = req.max_score
    if req.description is not None:
        result.description = req.description
    if req.result_image is not None:
        result.image_url = req.result_image

    db.commit()
    return {"message": "更新成功"}


@router.delete("/quizzes/{quiz_id}/ranges/{range_id}")
def delete_range(
    quiz_id: int,
    range_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """删除结果区间（前端桥接）"""
    result = db.query(QuizResult).filter(
        QuizResult.id == range_id,
        QuizResult.quiz_id == quiz_id,
    ).first()
    if not result:
        raise HTTPException(404, "结果区间不存在")

    db.delete(result)
    db.commit()
    return {"message": "删除成功"}
