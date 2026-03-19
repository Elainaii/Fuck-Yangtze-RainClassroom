import json


def read_log(file_path):
    """读取日志文件并返回为列表格式."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, list) else []
    except FileNotFoundError:
        print(f"文件 {file_path} 不存在，将返回空列表。")
        return []
    except json.JSONDecodeError:
        print(f"文件 {file_path} 不是有效的JSON格式，将返回空列表。")
        return []


def write_log(file_path, new_log):
    """将新的日志写入文件末尾."""
    try:
        # 读取现有数据
        data = read_log(file_path)
        # 添加新日志到末尾
        data.append(new_log)
        # 写入文件
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print("日志已成功写入文件末尾。")
    except Exception as e:
        print(f"写入文件时出错: {e}")
