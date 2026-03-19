import os
import time

import requests

import config
from util.timestamp import get_now

SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "session.txt")


def load_session():
    """从 session.txt 读取缓存的 SESSION"""
    if os.path.exists(SESSION_FILE):
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            session_id = f.read().strip()
            if session_id:
                return session_id
    return None


def save_session(session_id):
    """保存 SESSION 到 session.txt"""
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        f.write(session_id)
    print(f"[{get_now()}] SESSION 已保存到 {SESSION_FILE}")


def validate_session(session_id):
    """用 get_listening API 验证 SESSION 是否有效"""
    test_headers = {"Cookie": "sessionid=" + session_id}
    try:
        response = requests.get(
            config.host + config.api["get_listening"],
            headers=test_headers,
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json().get("data")
            if isinstance(data, dict):
                print(f"[{get_now()}] SESSION 验证通过")
                return True
            else:
                print(f"[{get_now()}] SESSION 已过期，API 返回: {data}")
                return False
        else:
            print(f"[{get_now()}] SESSION 验证失败，状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"[{get_now()}] SESSION 验证异常: {e}")
        return False


def _update_config_session(session_id):
    """原地更新 config.headers 中的 Cookie，传播到所有已导入的模块"""
    config.SESSION = session_id
    config.sessionId = session_id
    config.headers["Cookie"] = "sessionid=" + session_id


def auto_login(phone, password):
    """使用 DrissionPage 自动化浏览器登录雨课堂，返回 sessionid"""
    from DrissionPage import Chromium

    print(f"[{get_now()}] 正在启动浏览器进行登录...")

    browser = Chromium()
    tab = browser.latest_tab

    tab.get("https://changjiang.yuketang.cn/")

    # 点击"账号密码登录"图标
    change_img = tab.ele("css:img.changeImg")
    if change_img:
        change_img.click()
        time.sleep(1)
    else:
        print(f"[{get_now()}] 未找到账号密码登录入口，可能页面已变更")

    # 填入手机号和密码
    login_name_input = tab.ele("css:input[name=loginname]")
    password_input = tab.ele("css:input[name=password]")

    if login_name_input and password_input:
        login_name_input.clear()
        login_name_input.input(phone)
        password_input.clear()
        password_input.input(password)
        time.sleep(0.5)

        # 点击登录按钮
        login_btn = tab.ele("css:.login-btn")
        if login_btn:
            login_btn.click()
        else:
            print(f"[{get_now()}] 未找到登录按钮，请手动点击登录")
    else:
        print(f"[{get_now()}] 未找到登录输入框，请手动输入账号密码并登录")

    print(f"[{get_now()}] 如果出现验证码，请在浏览器中手动完成验证")

    # 轮询等待 cookies 中出现 sessionid，最长 120 秒
    timeout = 120
    start_time = time.time()
    session_id = None

    while time.time() - start_time < timeout:
        cookies = tab.cookies()
        for cookie in cookies:
            if cookie.get("name") == "sessionid":
                session_id = cookie["value"]
                break
        if session_id:
            break
        time.sleep(2)

    browser.quit()

    if session_id:
        print(f"[{get_now()}] 登录成功，已获取 SESSION")
        return session_id
    else:
        print(f"[{get_now()}] 登录超时（{timeout}s），未能获取 SESSION")
        return None


def ensure_session():
    """整合流程：加载 -> 验证 -> (无效则)登录 -> 保存 -> 更新 config.headers

    返回 True 表示 SESSION 可用，False 表示获取失败。
    """
    # 1. 尝试从缓存文件加载
    session_id = load_session()

    # 2. 如果有缓存，验证是否有效
    if session_id:
        if validate_session(session_id):
            _update_config_session(session_id)
            return True
        print(f"[{get_now()}] 缓存的 SESSION 已失效，尝试重新登录")

    # 3. 检查是否配置了手机号和密码
    phone = getattr(config, "PHONE", "")
    password = getattr(config, "PASSWORD", "")

    if not phone or not password:
        # 没有配置登录凭证，尝试用 config.py 中的 SESSION
        if config.SESSION:
            print(f"[{get_now()}] 使用 config.py 中配置的 SESSION")
            if validate_session(config.SESSION):
                save_session(config.SESSION)
                _update_config_session(config.SESSION)
                return True
            else:
                print(f"[{get_now()}] config.py 中的 SESSION 也已失效")
        print(f"[{get_now()}] 请在 config.py 中配置 PHONE 和 PASSWORD 以启用自动登录")
        return False

    # 4. 自动登录
    session_id = auto_login(phone, password)
    if session_id:
        save_session(session_id)
        _update_config_session(session_id)
        return True

    print(f"[{get_now()}] 自动登录失败")
    return False
