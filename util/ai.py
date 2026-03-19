import json
import threading

from google import genai
from google.genai import types as genai_types
from config import ai_key
from util.ocr import ocr_form_url_image

### 摘抄自一个学弟的第二课堂仓库AI部分
## https://github.com/tinyvan/SecondClass

system_prompt = """
我将为你发送类似如下格式的文本，question为使用OCR工具对图片题目识别的结果，你需要根据语义拼接，有的时候ABCD字符会缺失或者在选项后面，具体根据顺序和语义；
options提供选项（如果选项为空，请从question中寻找，如果question没有选项，只能蒙一个answers了），回答的时候必须根据type（例如type为单选题应该只给一个结果，type为填空题应该给文本，type为多选题应该给多个答案）
{
    "type": "单选题",
    "question": ['下面（）算法适合构造一个稠密图G的最小生成树', 'A.Prim算法', 'B.Kruskal算法', 'C.Floyd算法', 'D.Dijkstra算法'],
    "options": ["A","B","C","D"]
}
你应该回答：
{
"thinking":"你简洁的思考过程",
"answer":["A"]
}
如果question模糊不清，即使结合JSON的所有信息都无法辨别并给出答案。如果是选择题选A，填空题，主观题答“。。。”
如果是主观题，你的答案应该简洁明了，不使用逗号以外的标点符号，不使用markdown格式，控制在30字以内
"""

AI_TIMEOUT_SECONDS = 30

client = None
_init_lock = threading.Lock()


def _ensure_client():
    """线程安全的客户端初始化（双重检查锁），只创建一次。"""
    global client
    if client is not None:
        return
    with _init_lock:
        if client is not None:
            return
        client = genai.Client(
            api_key=ai_key,
            http_options=genai_types.HttpOptions(timeout=AI_TIMEOUT_SECONDS * 1000),
        )


def get_ans(text):
    _ensure_client()
    response = client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=text,
        config={
            "system_instruction": system_prompt,
            "response_mime_type": "application/json",
        },
    )
    return response.text


def _normalize_option(opt):
    """将选项统一为纯字符串 key。支持 {"key": "A", ...} 对象和纯字符串两种格式。"""
    if isinstance(opt, dict) and "key" in opt:
        return opt["key"]
    return opt


def _format_options_for_ai(options):
    """将选项列表格式化为 AI 可读的字符串列表，如 ["A.Activity", "B.Service"]。
    同时保留纯字符串格式的兼容。"""
    if not options:
        return options
    result = []
    for o in options:
        if isinstance(o, dict) and "key" in o:
            value = o.get("value", "")
            result.append(f"{o['key']}.{value}" if value else o["key"])
        else:
            result.append(o)
    return result


def _normalize_answer(answer):
    """将答案列表中的每个元素统一为纯字符串。"""
    if not isinstance(answer, list):
        return answer
    return [_normalize_option(a) for a in answer]


def _get_fallback_answer(type_name, options):
    """AI 超时或失败时返回默认答案。选择题选第一项，其他题型返回空。"""
    if type_name in ("单选题", "多选题", "投票题"):
        if options and len(options) > 0:
            return [_normalize_option(options[0])]
        return ["A"]
    return []


def request_ai(type, problem, options, img_url):
    problem_text = problem
    if problem == "":
        print("题目文本为空 启用OCR图片识别")
        problem_text = ocr_form_url_image(img_url)
        print("OCR识别结果", problem_text)

    # 发送给 AI 的选项格式化为 "A.内容" 形式，让 AI 能看到选项内容
    send = {
        "type": type,
        "question": problem_text,
        "options": _format_options_for_ai(options),
    }

    try:
        response = get_ans(str(send))
        print(response)
        answer = json.loads(response)["answer"]
        return _normalize_answer(answer)
    except Exception as e:
        print(f"AI请求失败: {e}，使用默认答案")
        return _get_fallback_answer(type, options)
