"""会员等级评分（独立版，不依赖 app.services）
从 member_scorer 移植核心逻辑 + 等级分段
"""
import re

CITY_SCORE = {
    "北京": 10, "上海": 10, "广州": 10, "深圳": 10,
    "杭州": 9, "成都": 9, "重庆": 8,
    "南京": 8, "西安": 8, "武汉": 8, "长沙": 8,
    "苏州": 7, "天津": 7, "东莞": 7, "佛山": 7,
}

def parse_income(raw):
    if not raw: return 5
    raw = str(raw).strip()
    static = {
        "30000以上": 40, "20000以上": 25, "15000-20000": 22,
        "10000-15000": 20, "8000-10000": 18, "5000-8000": 12,
        "3000-5000": 5, "3000以下": 0, "未工作/在读": 0,
    }
    if raw in static: return static[raw]
    nums = re.findall(r'\d+', raw)
    if nums:
        val = int(nums[0])
        if val >= 30000: return 40
        if val >= 20000: return 25
        if val >= 15000: return 22
        if val >= 10000: return 20
        if val >= 8000: return 18
        if val >= 5000: return 12
        if val >= 3000: return 5
        return 0
    return 5

def guess_age(m):
    bi = str(m.get("birth_info") or m.get("age") or "")
    years = re.findall(r'(19\d{2}|20\d{2})', bi)
    if years: return 2026 - int(years[0])
    ages = re.findall(r'(\d+)\s*岁', bi)
    if ages: return int(ages[0])
    a = m.get("age")
    if a and str(a).isdigit(): return int(a)
    return None

def city_score(city):
    if not city: return 2
    city = city.strip()
    if city in CITY_SCORE: return CITY_SCORE[city]
    for key, score in CITY_SCORE.items():
        if key in city or city in key: return score
    return 4

def compute_total_score(m):
    """0~100 分 → 映射到 S/A/B/C"""
    s = 0
    # 城市 (0-10)
    s += city_score(m.get("city", ""))
    # 年龄 (0-5)
    age = guess_age(m)
    if age:
        if 25 <= age <= 35: s += 5
        elif 20 <= age <= 45: s += 3
        else: s += 1
    else: s += 1
    # 身高 (0-10)
    h = m.get("height", "")
    if h:
        h_text = str(h).replace("cm","").strip()
        if h_text.isdigit():
            hv = int(h_text)
            if hv >= 180: s += 10
            elif hv >= 175: s += 8
            elif hv >= 170: s += 5
    # 学历 (0-10)
    edu = m.get("education", "")
    if edu in ("硕士","博士"): s += 10
    elif edu == "本科": s += 8
    elif edu == "大专": s += 4
    # 职业 (0-5)
    job = m.get("job", "")
    if job and job not in ("学生","无",""): s += 5
    # 收入 (0-10)
    s += min(parse_income(m.get("income","")) / 4, 10)
    # 资料完整度 (0-20)
    fields = ["city","age","job","education","height","body_type","role",
              "self_tags","ideal_desc","dealbreaker","extra"]
    filled = sum(1 for f in fields if m.get(f) and str(m.get(f,"")).strip())
    s += min(filled, 20)
    # 脱单态度 (0-5)
    att = str(m.get("attitude","") or m.get("理想型描述",""))
    if len(att) > 20: s += 5
    elif len(att) > 5: s += 3
    # 个人描述丰富度 (0-5)
    tags = str(m.get("self_tags",""))
    if len(tags) > 30: s += 5
    elif len(tags) > 10: s += 3
    # photo 加分
    if m.get("photo_path") or m.get("photos"):
        s += 5

    return s

def evaluate_level(m):
    """S(≥70) A(55~69) B(40~54) C(<40)"""
    score = compute_total_score(m)
    score = min(max(score, 0), 100)
    if score >= 70: return "S", score
    if score >= 55: return "A", score
    if score >= 40: return "B", score
    return "C", score
