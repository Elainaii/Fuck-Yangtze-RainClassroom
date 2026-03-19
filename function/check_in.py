import requests

from function.listening_socket import start_all_sockets
from function.user import get_user_name
from config import host, api, headers, log_file_name, check_in_sources
from util.file import write_log, read_log
from util.timestamp import get_now

# 正在监听的 lesson_id 集合，防止重复创建 WebSocket
_listening_lessons = set()


# 获取正在进行的
def get_listening():
    print(f"[{get_now()}] 正在查询课堂列表...")
    response = requests.get(host + api["get_listening"], headers=headers)
    print(f"[{get_now()}] API 响应状态码: {response.status_code}")
    if response.status_code == 200:
        response_data = response.json()
        data = response_data["data"]
        if not isinstance(data, dict):
            print(f"[{get_now()}] SESSION 可能已过期，API 返回: {data}")
            return None
        return data
    else:
        print(f"[{get_now()}] 请求失败: {response.status_code} {response.text}")
        return None


# 获取正在进行的课堂并且签到、写日志
def get_listening_classes_and_sign(filtered_courses: list):
    response = get_listening()
    if response is None:
        return None

    name = get_user_name()
    print(f"[{get_now()}] 当前用户: {name}")

    # 短期存储查看PPT用的JWT、lessonId等信息
    on_lesson_list = []

    classes = list(response["onLessonClassrooms"])
    exams = list(response.get("upcomingExam", []))

    # 清理已结束的课堂（API 不再返回的 lesson 说明已下课）
    active_lesson_ids = {item["lessonId"] for item in classes}
    ended = _listening_lessons - active_lesson_ids
    if ended:
        print(f"[{get_now()}] 以下课堂已结束，移出监听列表: {ended}")
        _listening_lessons.difference_update(ended)

    if exams:
        print(f"[{get_now()}] 发现 {len(exams)} 个即将到来的考试")
        for exam in exams:
            print(f"  - {exam}")

    if len(classes) == 0:
        print(f"[{get_now()}] 无课")
        return True

    print(f"[{get_now()}] 发现 {len(classes)} 个正在进行的课堂")
    for item in classes:
        course_name = item["courseName"]
        lesson_id = item["lessonId"]

        if lesson_id in _listening_lessons:
            print(f"[{get_now()}] {course_name} 已在监听中，跳过")
            continue

        print(f"[{get_now()}] 正在签到: {course_name} (lessonId={lesson_id})")

        response_sign = check_in_on_listening(lesson_id)

        if response_sign.status_code == 200:
            print(f"[{get_now()}] {course_name} 签到成功")
            data = response_sign.json()["data"]
            socket_jwt = data["lessonToken"]
            jwt = response_sign.headers["Set-Auth"]
            identity_id = data["identityId"]

            should_listen = len(filtered_courses) == 0 or course_name in filtered_courses
            if should_listen:
                on_lesson_list.append({
                    "ppt_jwt": jwt,
                    "socket_jwt": socket_jwt,
                    "lesson_id": lesson_id,
                    "identity_id": identity_id,
                    "course_name": course_name,
                })
                print(f"[{get_now()}] {course_name} 已加入答题监听队列")
            else:
                print(f"[{get_now()}] {course_name} 不在过滤列表中，仅签到")

            # 将签到信息写入日志
            new_log = {
                "id": lesson_id,
                "title": course_name,
                "name": course_name,
                "time": get_now(),
                "student": name,
                "status": "签到成功",
                "url": "https://changjiang.yuketang.cn/m/v2/lesson/student/" + str(lesson_id),
            }
            write_log(log_file_name, new_log)
        else:
            print(f"[{get_now()}] {course_name} 签到失败: {response_sign.status_code} {response_sign.text}")

    # 所有签到完成后，启动 WebSocket 监听
    if on_lesson_list:
        print(f"[{get_now()}] 启动 {len(on_lesson_list)} 个 WebSocket 监听线程")
        start_all_sockets(on_lesson_list)
        for item in on_lesson_list:
            _listening_lessons.add(item["lesson_id"])
    else:
        print(f"[{get_now()}] 无需监听的课程")

    return True


# 传入lessonId 签到
def check_in_on_listening(lesson_id):
    sign_data = {
        "source": check_in_sources["二维码"],
        "lessonId": str(lesson_id),
        "joinIfNotIn": True,
    }
    response_sign = requests.post(host + api["sign_in_class"], headers=headers, json=sign_data)
    return response_sign
