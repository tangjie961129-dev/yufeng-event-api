"""
问卷引擎公开 API

恋爱脱单测评(quiz_type=match)的最终结果使用匹配引擎计算
70-95 分的市场匹配分, 用于销售话术: 系统里有大量符合你要求的会员.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import get_current_user, get_optional_user
from app.models.user import User
from app.models.quiz import Quiz, QuizQuestion, QuizResult, QuizSubmission
from app.models.member_profile import MemberProfile

router = APIRouter(prefix="/api", tags=["问卷引擎"])


# ====== Schemas ======

class AnswerItem(BaseModel):
    question_id: int
    answer: object  # str for single_choice/scale, list for multi_choice


class SubmitAnswersRequest(BaseModel):
    answers: List[AnswerItem]




def _option_label(opt: dict) -> str:
    return str(opt.get("label") or opt.get("value") or "")

def _serialize_question(q: QuizQuestion) -> dict:
    options = q.options or []
    qtype = q.question_type or "single_choice"
    frontend_type = qtype
    if qtype == "single_choice":
        frontend_type = "picker"
    elif qtype == "multi_choice":
        frontend_type = "tags"
    return {
        "id": q.id,
        "question_text": q.question_text,
        "question_type": q.question_type,
        "sort_order": q.sort_order,
        "options": options,
        "required": q.required,
        "field_key": q.field_key or ("q_" + str(q.id)),
        "placeholder": q.placeholder or "",
        "input_type": q.input_type or "text",
        "maxlength": q.maxlength or 200,
        "suffix": q.suffix or "",
        "use_native_picker": bool(q.use_native_picker),
        "help_text": q.help_text or "",
        # 小程序直接可消费字段
        "field": q.field_key or ("q_" + str(q.id)),
        "label": q.question_text,
        "type": frontend_type,
        "inputType": q.input_type or "text",
        "pickerRange": [_option_label(o) for o in options],
        "tags": [_option_label(o) for o in options],
        "useNativePicker": bool(q.use_native_picker),
    }

def _serialize_result(result: QuizResult | None) -> dict | None:
    if not result:
        return None
    return {
        "id": result.id,
        "title": result.title,
        "description": result.description,
        "content": result.content,
        "image_url": result.image_url,
        "type": result.result_type or result.title,
        "result_type": result.result_type or "",
        "traits": result.traits or [],
        "scores": result.scores or {},
        "cta_title": result.cta_title or "",
        "cta_desc": result.cta_desc or "",
        "qrcode_url": result.qrcode_url or "",
        "share_text": result.share_text or "",
        "min_score": result.min_score,
        "max_score": result.max_score,
    }

# ====== Public APIs ======

@router.get("/quizzes")
def list_quizzes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    quiz_type: str = "",
    db: Session = Depends(get_db),
):
    """公开问卷列表（只返回已发布）"""
    query = db.query(Quiz).filter(Quiz.is_published == True)

    if quiz_type:
        query = query.filter(Quiz.quiz_type == quiz_type)

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
            "image_url": q.image_url,
            "created_at": q.created_at,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/quizzes/by-type/{quiz_type}")
def get_quiz_by_type(
    quiz_type: str,
    db: Session = Depends(get_db),
):
    """小程序按业务类型读取已发布问卷：mbti/lgti/match/portrait。"""
    quiz = db.query(Quiz).filter(Quiz.quiz_type == quiz_type, Quiz.is_published == True).order_by(Quiz.id.desc()).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")
    return get_quiz_detail(quiz.id, db)


@router.get("/quizzes/{quiz_id}")
def get_quiz_detail(
    quiz_id: int,
    db: Session = Depends(get_db),
):
    """问卷详情（含题目列表）"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.is_published == True).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    questions = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_id == quiz_id
    ).order_by(QuizQuestion.sort_order.asc(), QuizQuestion.id.asc()).all()

    questions_data = []
    for q in questions:
        questions_data.append(_serialize_question(q))

    return {
        "id": quiz.id,
        "title": quiz.title,
        "description": quiz.description,
        "quiz_type": quiz.quiz_type,
        "questions_count": quiz.questions_count,
        "image_url": quiz.image_url,
        "created_at": quiz.created_at,
        "questions": questions_data,
    }


def _compute_score(questions: list, answers: list) -> float:
    """
    计算问卷总得分。
    - single_choice: score = 选中项的score值
    - multi_choice: score = 所有选中项score之和
    - scale: score = 所选数值
    """
    total_score = 0.0
    q_map = {q.id: q for q in questions}

    for ans in answers:
        question = q_map.get(ans.question_id)
        if not question:
            continue

        if question.question_type == "single_choice":
            # answer is a string value (the selected option value/label)
            options = question.options or []
            for opt in options:
                if opt.get("value") == ans.answer or opt.get("label") == ans.answer:
                    total_score += float(opt.get("score", 0))
                    break

        elif question.question_type == "multi_choice":
            # answer is a list of selected values
            selected = ans.answer if isinstance(ans.answer, list) else []
            options = question.options or []
            opt_map = {o.get("value", o.get("label")): o for o in options}
            for sel in selected:
                opt = opt_map.get(sel)
                if opt:
                    total_score += float(opt.get("score", 0))

        elif question.question_type == "scale":
            # answer is a numeric value (1-5 or 1-10)
            try:
                total_score += float(ans.answer)
            except (TypeError, ValueError):
                pass

    return total_score


def _extract_answer(answers: list, id_to_field: dict, field_key: str, default=""):
    """从答案列表中按 field_key 提取单个值。"""
    for ans in answers:
        field = id_to_field.get(ans.question_id, "")
        if field == field_key:
            val = ans.answer
            if isinstance(val, list):
                return val[0] if val else default
            return str(val) if val else default
    return default


def _extract_answer_list(answers: list, id_to_field: dict, field_key: str) -> list:
    """从答案列表中按 field_key 提取多选值列表。"""
    for ans in answers:
        field = id_to_field.get(ans.question_id, "")
        if field == field_key:
            val = ans.answer
            if isinstance(val, list):
                return [str(v) for v in val if v]
            return [str(val)] if val else []
    return []


def _compute_match_market_score(db: Session, quiz: Quiz, questions: list, answers: list) -> int:
    """
    基于匹配引擎计算恋爱脱单测评的市场匹配分.

    原理:
    1. 从测评答案中提取用户偏好(城市/年龄/角色/标签等)
    2. 查询 member_profiles 会员库中匹配的候选人
    3. 根据匹配数量和质量映射到 70-95 销售友好分

    返回一个 70-95 之间的整数分, 用于对外话术:
    "系统里有大量符合你要求的会员, 你还有 {85}% 的提升空间"
    """
    # 1. 提取用户偏好
    id_to_field = {q.id: (q.field_key or f"q{q.id}") for q in questions}

    city = _extract_answer(answers, id_to_field, "city", "")
    age_group = _extract_answer(answers, id_to_field, "age_group", "")
    role_self = _extract_answer(answers, id_to_field, "role_self", "")
    long_distance = _extract_answer(answers, id_to_field, "long_distance", "")
    partner_tags = _extract_answer_list(answers, id_to_field, "partner_tags")
    accept_long_dist = long_distance not in ("不接受", "")

    # 2. 构建候选人查询
    base = db.query(MemberProfile).filter(MemberProfile.nickname != "")

    filters = []
    if city:
        filters.append(MemberProfile.city.ilike(f"%{city}%"))
    if age_group:
        age_map = {"18-22": (18, 22), "23-27": (23, 27), "28-32": (28, 32),
                   "33-38": (33, 38), "39-45": (39, 45), "45以上": (45, 60)}
        ar = age_map.get(age_group, (18, 60))
        filters.append(MemberProfile.age.between(ar[0], ar[1]))
    if role_self and role_self not in ("都可以", ""):
        compatible = {
            "1":    ["0", "0.5", "side"],
            "0":    ["1", "0.5", "side"],
            "0.5":  ["0", "1", "0.5", "side"],
            "side": ["0", "1", "0.5", "side"],
        }.get(role_self, [])
        if compatible:
            filters.append(MemberProfile.role_self.in_(compatible))

    if filters:
        candidates = base.filter(*filters).all()
        if not candidates:
            # 放宽: 仅按城市过滤
            candidates = base.filter(*filters[:1]).limit(30).all() if filters else []
        if not candidates:
            candidates = base.limit(30).all()
    else:
        candidates = base.limit(30).all()

    total = len(candidates)
    if total == 0:
        return 72  # 最低保底, 保持销售积极

    # 3. 计算每位候选人的匹配质量
    high_quality = 0  # 强匹配: 角色兼容 + 同城 + 年龄相仿
    good_quality = 0   # 可选匹配

    for c in candidates:
        q = 0

        # 角色兼容性 (满分 35)
        cr = c.role_self or ""
        if role_self and cr:
            if role_self == "0.5" or cr == "0.5":
                q += 35  # 0.5 可兼容任何角色
            elif (role_self == "1" and cr in ("0", "0.5", "side")) or \
                 (role_self == "0" and cr in ("1", "0.5", "side")) or \
                 (role_self == "side" and cr in ("0", "0.5", "1")):
                q += 35
            elif role_self == cr:
                q += 15
            elif role_self and cr:
                q += 5  # 不兼容但也不淘汰

        # 同城评分 (满分 30)
        if city and c.city:
            if city in c.city or c.city in city:
                q += 30

        # 年龄相仿 (满分 20)
        if age_group and c.age:
            center_map = {"18-22": 20, "23-27": 25, "28-32": 30,
                          "33-38": 35, "39-45": 42, "45以上": 50}
            center = center_map.get(age_group, 28)
            diff = abs(center - c.age)
            if diff <= 3:
                q += 20
            elif diff <= 6:
                q += 14
            elif diff <= 10:
                q += 8
            else:
                q += 4
        else:
            q += 10  # 年龄未知给了中等分

        # 资料完整度 (满分 15)
        completeness = sum(1 for f in [c.nickname, c.city, c.age, c.job, c.hobbies] if f)
        q += completeness * 3

        if q >= 70:
            high_quality += 1
            good_quality += 1
        elif q >= 45:
            good_quality += 1

    # 4. 计算最终销售友好分 (70-95)
    # 高质量候选人 1个=2分, 可选候选人 1个=1分, cap at 30有效值
    effective = high_quality * 2 + good_quality
    capped = min(effective, 30)
    ratio = capped / 30.0  # 0.0 ~ 1.0
    score = 70 + ratio * 25
    score = max(70, min(95, round(score)))
    return score


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(
    quiz_id: int,
    req: SubmitAnswersRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交问卷答案 → 计算分数 → 匹配结果区间 → 返回结果"""
    quiz = db.query(Quiz).filter(Quiz.id == quiz_id, Quiz.is_published == True).first()
    if not quiz:
        raise HTTPException(404, "问卷不存在")

    questions = db.query(QuizQuestion).filter(
        QuizQuestion.quiz_id == quiz_id
    ).all()

    if not questions:
        raise HTTPException(400, "该问卷没有题目")

    # 计算分数
    raw_score = _compute_score(questions, req.answers)

    # 匹配结果区间
    result = db.query(QuizResult).filter(
        QuizResult.quiz_id == quiz_id,
        QuizResult.min_score <= raw_score,
        QuizResult.max_score >= raw_score,
    ).first()

    # 如果是恋爱脱单测评(match类型), 改用匹配引擎计算市场匹配分(70-95)
    if quiz.quiz_type == "match":
        display_score = _compute_match_market_score(db, quiz, questions, req.answers)
    else:
        display_score = raw_score

    # 保存提交记录(存原始分)
    submission = QuizSubmission(
        quiz_id=quiz_id,
        user_id=current_user.id,
        answers=[a.model_dump() for a in req.answers],
        score=raw_score,
        result_id=result.id if result else None,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    result_data = None
    if result:
        result_data = _serialize_result(result)

    return {
        "submission_id": submission.id,
        "score": display_score,
        "result": result_data,
        "quiz_type": quiz.quiz_type,
    }


@router.get("/love/test/result")
def get_latest_test_result(
    quiz_type: str = Query("", description="筛选问卷类型: mbti / lgti / custom"),
    current_user: User = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """兼容接口：根据 quiz_type 查询用户最近一次测试结果"""
    if not current_user:
        raise HTTPException(401, "请先登录")

    query = db.query(QuizSubmission).join(
        Quiz, QuizSubmission.quiz_id == Quiz.id
    ).filter(
        QuizSubmission.user_id == current_user.id,
    )

    if quiz_type:
        query = query.filter(Quiz.quiz_type == quiz_type)

    submission = query.order_by(QuizSubmission.created_at.desc()).first()
    if not submission:
        raise HTTPException(404, "未找到测试记录")

    # 获取关联的问卷和结果
    quiz = db.query(Quiz).filter(Quiz.id == submission.quiz_id).first()
    result = None
    if submission.result_id:
        result = db.query(QuizResult).filter(QuizResult.id == submission.result_id).first()

    result_data = None
    if result:
        result_data = _serialize_result(result)

    # 对 match 类型的测评, 用匹配引擎重新计算市场匹配分
    display_score = submission.score
    if quiz and quiz.quiz_type == "match":
        try:
            questions = db.query(QuizQuestion).filter(
                QuizQuestion.quiz_id == quiz.id
            ).all()
            # 从submission.answers重建AnswerItem列表
            from pydantic import BaseModel
            class _Ans(BaseModel):
                question_id: int
                answer: object
            ans_items = [_Ans(**a) for a in (submission.answers or [])]
            display_score = _compute_match_market_score(db, quiz, questions, ans_items)
        except Exception:
            display_score = submission.score  # fallback

    return {
        "submission_id": submission.id,
        "quiz_id": submission.quiz_id,
        "quiz_title": quiz.title if quiz else "",
        "quiz_type": quiz.quiz_type if quiz else "",
        "score": display_score,
        "result": result_data,
        "created_at": submission.created_at,
    }
