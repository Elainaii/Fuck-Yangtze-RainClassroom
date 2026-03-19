# 长江雨课堂定时签到+听课答题

### 🚀 开始配置
1.复制config_example.py为config.py

2.填写config.py

3.安装依赖
```bash
uv sync
```

4.配置config.py中
```python
filtered_courses=[
        # 默认为空 所有课题监听课程测试
        # 若填写课程名称 则只监听列表里的课，其余课仅签到,建议按自己需求添加
        "计算机组成原理","数据结构"
]
```

5.定时运行start.py(推荐使用宝塔面板定时任务，具体教程自行搜索)
```bash
python start.py
```


## 获取SESSIONID方式

下面是手动获取，脚本支持填写账号密码自动获取

访问 https://changjiang.yuketang.cn/ ,登录后，按F12
![图片1](src/screenShot/1.png)
![图片2](src/screenShot/2.png)
![图片3](src/screenShot/3.png)
![图片4](src/screenShot/4.png)

复制粘贴得到的id到config.txt，并保存即可

## [获取AI_KEY(AI 用于解题或辅助题库搜题规格化答案)](https://api.chatanywhere.org/v1/oauth/free/render)

