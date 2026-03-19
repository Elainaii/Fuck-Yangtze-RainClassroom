import time
import threading

from config import filtered_courses, CHECK_INTERVAL
from function.check_in import get_listening_classes_and_sign
from util.login import ensure_session
from util.timestamp import get_now

def main():
    print(f"[{get_now()}] 程序启动，正在检查 SESSION...")

    if not ensure_session():
        print(f"[{get_now()}] 无法获取有效的 SESSION，程序退出")
        return

    print(f"[{get_now()}] SESSION 就绪，每 {CHECK_INTERVAL} 秒检查一次课堂状态")
    print(f"[{get_now()}] 过滤课程: {filtered_courses if filtered_courses else '无(监听所有课程)'}")

    while True:
        print(f"\n[{get_now()}] === 开始检查 ===")
        try:
            result = get_listening_classes_and_sign(filtered_courses)
            # SESSION 过期时 get_listening 返回 None
            if result is None:
                print(f"[{get_now()}] SESSION 可能已过期，尝试重新获取...")
                if ensure_session():
                    print(f"[{get_now()}] SESSION 已更新，下次检查将使用新 SESSION")
                else:
                    print(f"[{get_now()}] 重新获取 SESSION 失败，将在下次检查时重试")
        except Exception as e:
            print(f"[{get_now()}] 检查异常: {e}")

        # 等待已启动的 WebSocket 监听线程列表（非守护线程会自行运行）
        active = threading.active_count() - 1  # 减去主线程
        if active > 0:
            print(f"[{get_now()}] 当前有 {active} 个 WebSocket 监听线程运行中")

        print(f"[{get_now()}] === 检查结束，{CHECK_INTERVAL} 秒后再次检查 ===")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
