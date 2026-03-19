# 长江雨课堂定时签到+听课答题

### 🚀 开始配置
1.按下面教程拿到SESSIONID，或者自己抓APP的包

2.按图中路径，配置名为SESSION的环境变量，值为SESSIONID的值
![图片1](src/img/Step_1.png)
![图片2](src/img/Step_2.png)

3.继续在设置中，修改选项(为了写入日志)
![图片3](src/img/Step_3.png)


4.再配置两个secret，AI_KEY和ENNCY_KEY，用于搜题答题，获取方式在末尾

5.再配置一个secret，FILTERED_COURSES，用英文逗号隔开，不要有空格，填写需要一直监听答题的课程，为空则代表所有课程都监听

例如：计算机组成原理,数据结构

6.去Action板块Run,观察运行结果，检查是否通过
![图片4](src/img/Step_4.png)

### 🚀 开始配置
1.进入config.py

2.填写config

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

访问 https://changjiang.yuketang.cn/ ,登录后，按F12
![图片1](src/screenShot/1.png)
![图片2](src/screenShot/2.png)
![图片3](src/screenShot/3.png)
![图片4](src/screenShot/4.png)

复制粘贴得到的id到config.txt，并保存即可

## [获取AI_KEY(AI 用于解题或辅助题库搜题规格化答案)](https://api.chatanywhere.org/v1/oauth/free/render)
## [获取ENNCY_KEY(言溪题库 用于题目为空时搜题)](https://tk.enncy.cn/)

