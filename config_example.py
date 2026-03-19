# =============================================================
# 用户配置区域 - 请在此处修改你的配置
# =============================================================

# 登录凭证 - 手机号和密码（配置后可自动登录获取 SESSION）
PHONE = ""
PASSWORD = ""

# SESSION（一般无需手动填写，程序会自动获取并缓存到 session.txt）
# 如果不想使用自动登录，也可以手动填写从浏览器 Cookie 中获取的 sessionid
SESSION = ""

# Gemini API Key (从 https://aistudio.google.com/apikey 获取)
AI_KEY = ""

# 课程过滤列表
# 默认为空列表: 所有课程都会监听答题
# 若填写课程名称: 则只监听列表里的课，其余课仅签到
FILTERED_COURSES = [
    "软件工程与实践",
    "毛泽东思想和中国特色社会主义理论体系概论",
    "123"
]

# 轮询间隔（秒），每隔多久检查一次是否有课
CHECK_INTERVAL = 300

# =============================================================
# 以下为系统配置，一般不需要修改
# =============================================================

host = "https://changjiang.yuketang.cn/"

api = {
    "get_received": "api/v3/activities/received/",
    "get_published": "api/v3/activities/published/",
    "sign_in_class": "api/v3/lesson/checkin",
    "login_user": "pc/login/verify_pwd_login/",
    "user_info": "v2/api/web/userinfo",
    "class_info": "m/v2/lesson/student/",
    "get_listening": "api/v3/classroom/on-lesson-upcoming-exam",
    "get_ppt": "api/v3/lesson/presentation/fetch?presentation_id={}",
    "websocket": "wss://changjiang.yuketang.cn/wsapp/",
    "answer": "api/v3/lesson/problem/answer",
}

log_file_name = "log.json"

headers = {
    "Cookie": "sessionid=" + SESSION,
}

question_type = {
    1: "单选题",
    2: "多选题",
    3: "投票题",
    4: "填空题",
    5: "主观题",
}

check_in_sources = {
    "公众号": 5,
    "二维码": 21,
    "暗号": 22,
    "APP": 23,
}

# 向后兼容别名
sessionId = SESSION
ai_key = AI_KEY
filtered_courses = FILTERED_COURSES
