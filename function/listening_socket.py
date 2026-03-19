import threading
import concurrent.futures
import time

import requests
import websocket
import json
from config import host, api, headers, question_type
from util.ai import request_ai
from util.timestamp import get_date_time, get_now

ANSWER_TIMEOUT_SECONDS = 30
POLL_INTERVAL = 30
PRESENTATION_REFETCH_COOLDOWN = 5  # presentation 事件触发重新获取 PPT 的冷却时间（秒）
PRECOMPUTE_MAX_RETRIES = 3
PRECOMPUTE_RETRY_DELAY = 3  # 重试间隔（秒）


def _normalize_option(opt):
    if isinstance(opt, dict) and "key" in opt:
        return opt["key"]
    return opt


def _get_fallback_result(problem_type, options):
    if problem_type in (1, 2, 3):
        if options and len(options) > 0:
            return [_normalize_option(options[0])]
        return ["A"]
    return []


def _do_ai_request(problem_type, problem_content, options, img_url):
    return request_ai(
        type=question_type[problem_type],
        problem=problem_content,
        options=options,
        img_url=img_url,
    )


def on_message_connect(ppt_jwt, lesson_id, identity_id, socket_jwt, course_name):
    problem_list = dict()       # q_id -> 题目元数据
    precomputed = dict()        # q_id -> AI 预计算的答案列表
    precompute_futures = dict() # q_id -> Future (正在计算中)
    fetched_pres_ids = set()
    answered_ids = set()
    refetch_requested = set()   # 已触发过 PPT 重新获取的 q_id，防止无限循环
    poll_timer = [None]
    last_pres_refetch_time = [0.0]  # 上次因 presentation 事件触发重新获取的时间
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def log(msg):
        print(f"[{get_now()}] [{course_name}] {msg}")

    def safe_send(ws, data):
        try:
            ws.send(json.dumps(data))
        except Exception as e:
            log(f"WebSocket 发送失败: {e}")

    def send_hello(ws):
        safe_send(ws, {
            "op": "hello",
            "userid": identity_id,
            "role": "student",
            "auth": socket_jwt,
            "lessonid": lesson_id
        })

    def send_fetchtimeline(ws):
        safe_send(ws, {
            "op": "fetchtimeline",
            "lessonid": str(lesson_id),
            "msgid": 1
        })

    def cancel_poll():
        if poll_timer[0] is not None:
            poll_timer[0].cancel()
            poll_timer[0] = None

    def schedule_poll(ws, delay=POLL_INTERVAL):
        cancel_poll()
        def do_poll():
            log(f"定时重新检查（{delay}s 已过）...")
            send_fetchtimeline(ws)
        poll_timer[0] = threading.Timer(delay, do_poll)
        poll_timer[0].daemon = True
        poll_timer[0].start()
        log(f"等待推送中（{delay}s 后自动重查）...")

    def precompute_answer(q_id, problem):
        """后台预计算一道题的答案，失败自动重试"""
        p_type = problem["type"]
        p_content = problem["content"]
        p_options = problem["options"]
        p_img = problem["img_url"]
        type_name = question_type.get(p_type, p_type)
        log(f"[预计算] 开始: {type_name} - {p_content[:40]}")
        for attempt in range(1, PRECOMPUTE_MAX_RETRIES + 1):
            if q_id in answered_ids:
                log(f"[预计算] 题目已被答过，取消")
                return
            try:
                result = _do_ai_request(p_type, p_content, p_options, p_img)
                precomputed[q_id] = result
                log(f"[预计算] 完成: {type_name} - {p_content[:40]} -> {result}")
                return
            except Exception as e:
                if attempt < PRECOMPUTE_MAX_RETRIES:
                    log(f"[预计算] 第 {attempt} 次失败: {e}，{PRECOMPUTE_RETRY_DELAY}s 后重试...")
                    time.sleep(PRECOMPUTE_RETRY_DELAY)
                else:
                    log(f"[预计算] 第 {attempt} 次失败: {e}，已达最大重试次数，将在答题时现场计算")

    def start_precompute(q_id, problem):
        """提交预计算任务到线程池"""
        if q_id in precomputed or q_id in precompute_futures or q_id in answered_ids:
            return
        future = executor.submit(precompute_answer, q_id, problem)
        precompute_futures[q_id] = future

    def get_answer_result(q_id, problem):
        """获取答案：优先用预计算结果，否则等待或现场计算"""
        # 已有预计算结果
        if q_id in precomputed:
            log(f"使用预计算答案")
            return precomputed.pop(q_id)

        # 正在预计算中，等待完成
        future = precompute_futures.get(q_id)
        if future is not None:
            log(f"预计算进行中，等待完成...")
            try:
                future.result(timeout=ANSWER_TIMEOUT_SECONDS)
                if q_id in precomputed:
                    return precomputed.pop(q_id)
            except concurrent.futures.TimeoutError:
                log(f"等待预计算超时，使用默认答案")
                return _get_fallback_result(problem["type"], problem["options"])
            except Exception as e:
                log(f"预计算异常: {e}")

        # 没有预计算，现场计算（兜底）
        log(f"无预计算结果，现场调用 AI...")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                f = pool.submit(
                    _do_ai_request, problem["type"], problem["content"],
                    problem["options"], problem["img_url"]
                )
                return f.result(timeout=ANSWER_TIMEOUT_SECONDS)
        except concurrent.futures.TimeoutError:
            log(f"AI 请求超时，使用默认答案")
            return _get_fallback_result(problem["type"], problem["options"])
        except Exception as e:
            log(f"AI 请求失败: {e}，使用默认答案")
            return _get_fallback_result(problem["type"], problem["options"])

    def submit_answer(q_id, problem):
        """获取答案并提交"""
        type_name = question_type.get(problem["type"], problem["type"])
        log(f"开始答题: {type_name} - {problem['content'][:50]}")

        result = get_answer_result(q_id, problem)
        # 确保 result 中的每个元素都是纯字符串，防止提交对象导致服务器 500
        result = [_normalize_option(r) for r in result] if isinstance(result, list) else result

        post_json = {
            "problemId": q_id,
            "problemType": problem["type"],
            "dt": get_date_time(),
            "result": result,
        }

        new_headers = headers.copy()
        new_headers["Authorization"] = "Bearer " + ppt_jwt
        new_headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0")

        log(f"提交答案请求: POST {host + api['answer']}")
        log(f"  请求体: {json.dumps(post_json, ensure_ascii=False)}")

        response = requests.post(url=host + api["answer"], json=post_json, headers=new_headers)

        if response.status_code == 200:
            log(f"答题成功: {type_name} -> {result}")
        else:
            resp_text = response.text[:500]
            try:
                resp_json = response.json()
                msg = resp_json.get("msg", "未知错误")
            except Exception:
                resp_json = None
                msg = f"HTTP {response.status_code}"
            if msg == "LESSON_END":
                log(f"答题失败: 题目已经结束")
            else:
                log(f"答题失败: {msg}")
            log(f"  状态码: {response.status_code}")
            log(f"  响应头: {dict(response.headers)}")
            log(f"  响应体: {resp_text}")

    def on_message(ws, message):
        # 下课 结束监听
        if "lessonfinished" in message:
            cancel_poll()
            log("下课了，关闭连接")
            ws.close()
            return

        if "livestatus" not in message:
            data = json.loads(message)

            # 无 timeline → 服务器推送消息
            if "timeline" not in data:
                if "problem" in data or "unlockedproblem" in data:
                    cancel_poll()
                    log("收到题目推送，立即检查...")
                    send_fetchtimeline(ws)
                elif "presentation" in data:
                    pres_id = data.get("presentation")
                    op = data.get("op", "?")
                    event = data.get("event")
                    event_str = f", event={event}" if event else ""
                    log(f"收到 presentation 事件: op={op}, presentation={pres_id}{event_str}")
                    log(f"  完整数据: {json.dumps(data, ensure_ascii=False)}")

                    now = time.time()
                    elapsed = now - last_pres_refetch_time[0]
                    if elapsed >= PRESENTATION_REFETCH_COOLDOWN:
                        last_pres_refetch_time[0] = now
                        log(f"  PPT 可能有变化，重新获取（上次 {elapsed:.0f}s 前）...")
                        fetched_pres_ids.clear()
                        send_hello(ws)
                    else:
                        remaining = PRESENTATION_REFETCH_COOLDOWN - elapsed
                        log(f"  冷却中（还需 {remaining:.0f}s），跳过重新获取")
                else:
                    log(f"收到其他消息: {list(data.keys())}")
                    log(f"  完整数据: {json.dumps(data, ensure_ascii=False)}")
                return

            # fetchtimeline 响应
            cancel_poll()
            time_lines = [item for item in data["timeline"] if item.get("type") == "problem"]

            if len(time_lines) == 0:
                log("目前无题目，等待推送...")
                schedule_poll(ws)
                return

            # 从最新往最旧找第一道未处理的题目
            q_id = None
            for item in reversed(time_lines):
                if item["prob"] not in answered_ids:
                    q_id = item["prob"]
                    break

            if q_id is None:
                log("所有题目已处理，等待新题目推送...")
                schedule_poll(ws)
                return

            problem = problem_list.get(q_id)
            if problem is not None:
                try:
                    submit_answer(q_id, problem)
                except Exception as e:
                    log(f"答题流程异常: {e}，将在下次重试")
                    schedule_poll(ws)
                    return
                problem_list.pop(q_id, None)
                precompute_futures.pop(q_id, None)
                precomputed.pop(q_id, None)
                answered_ids.add(q_id)
                send_fetchtimeline(ws)
            else:
                if q_id not in refetch_requested:
                    log(f"题目 {q_id} 不在待答列表中，重新获取PPT...")
                    refetch_requested.add(q_id)
                    fetched_pres_ids.clear()
                    send_hello(ws)
                else:
                    log(f"题目 {q_id} PPT中未找到，30s后重试...")
                    refetch_requested.discard(q_id)
                    schedule_poll(ws)
        else:
            # hello 响应，获取PPT内容
            data = json.loads(message)
            ppt_ids = set()
            if "timeline" in data:
                for item in data["timeline"]:
                    if item.get("type") == "slide":
                        ppt_ids.add(item["pres"])
            else:
                log(f"hello 响应中无 timeline: {list(data.keys())}")

            new_ppt_ids = ppt_ids - fetched_pres_ids
            if not new_ppt_ids and fetched_pres_ids:
                log(f"PPT 未变化（已获取 {len(fetched_pres_ids)} 个）")
            elif new_ppt_ids:
                log(f"发现 {len(new_ppt_ids)} 个新 PPT，开始获取题目...")
                new_headers = headers.copy()
                new_headers["Authorization"] = "Bearer " + ppt_jwt
                new_headers["User-Agent"] = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/129.0.0.0 Safari/537.36 Edg/129.0.0.0")

                for pres_id in new_ppt_ids:
                    url = host + api["get_ppt"].format(pres_id)
                    log(f"获取 PPT: pres_id={pres_id}")
                    response = requests.get(headers=new_headers, url=url)
                    if response.status_code == 200:
                        ppt_pages = response.json()["data"]["slides"]
                        saved_count = 0
                        for ppt in ppt_pages:
                            if "problem" in ppt:
                                question = ppt["problem"]
                                q_id = question["problemId"]
                                if q_id in problem_list or q_id in answered_ids:
                                    continue
                                options = None
                                q_type = question["problemType"]
                                if q_type in (1, 2, 3):
                                    options = question["options"]
                                answered = list(question["answers"])
                                if len(answered) == 0:
                                    save_dict = {
                                        "type": q_type,
                                        "content": question["body"],
                                        "options": options,
                                        "img_url": ppt["coverAlt"]
                                    }
                                    problem_list[q_id] = save_dict
                                    saved_count += 1
                                    type_name = question_type.get(q_type, q_type)
                                    log(f"保存题目: {type_name} - {question['body'][:50]}")
                                    # 立即启动后台预计算
                                    start_precompute(q_id, save_dict)
                        log(f"PPT pres_id={pres_id} 处理完成，新增 {saved_count} 题")
                        fetched_pres_ids.add(pres_id)
                    else:
                        log(f"获取 PPT 失败: pres_id={pres_id}, 状态码={response.status_code}")

            precomputing = sum(1 for f in precompute_futures.values() if not f.done())
            precomputed_count = len(precomputed)
            log(f"题目状态: {len(problem_list)} 题待答, {precomputed_count} 题已预计算, {precomputing} 题预计算中")
            send_fetchtimeline(ws)

    return on_message


def on_error(ws, error):
    print(f"[{get_now()}] WebSocket 错误: {error}")


def on_close(ws, close_status_code, close_msg):
    print(f"[{get_now()}] WebSocket 连接关闭 (code={close_status_code})")


def on_open_connet(jwt, lesson_id, identity_id):
    def on_open(ws):
        auth_payload = {
            "op": "hello",
            "userid": identity_id,
            "role": "student",
            "auth": jwt,
            "lessonid": lesson_id
        }
        ws.send(json.dumps(auth_payload))

    return on_open


def start_socket_ppt(ppt_jwt, socket_jwt, lesson_id, identity_id, course_name):
    print(f"[{get_now()}] [{course_name}] WebSocket 连接中...")
    ws = websocket.WebSocketApp(
        url=api["websocket"],
        on_open=on_open_connet(lesson_id=lesson_id, identity_id=identity_id, jwt=socket_jwt),
        on_message=on_message_connect(ppt_jwt=ppt_jwt, lesson_id=lesson_id, identity_id=identity_id,
                                      socket_jwt=socket_jwt, course_name=course_name),
        on_error=on_error,
        on_close=on_close,
    )

    ws.run_forever()


def start_all_sockets(on_lesson_list):
    threads = []

    for item in on_lesson_list:
        t = threading.Thread(
            target=start_socket_ppt,
            kwargs={
                "ppt_jwt": item["ppt_jwt"],
                "socket_jwt": item["socket_jwt"],
                "lesson_id": item["lesson_id"],
                "identity_id": item["identity_id"],
                "course_name": item["course_name"],
            }
        )
        t.start()
        threads.append(t)
