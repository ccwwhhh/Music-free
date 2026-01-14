# Music-free——基于Openagents的multi-agents音乐创作项目

based on https://github.com/openagents-org/openagents

## 功能特点
###基础功能（在原openagents基础上增加）
- **录音** 
- **音频文件生成**
 
###进阶功能
- **想法记录**：用户在聊天频道通过录音功能内哼歌
- **音频规范**：分析用户音频，生成格式化midi文件
- **乐谱生成**：将用户哼歌转化成数字简谱，并供用户选择播放的乐器、伴奏
- **乐谱优化**：利用大模型给出现有简谱优化建议
- **新闻检索**：检索音乐新闻并排版生成海报

###使用的Agent
| 名字  |  功能 |  响应方式  |
| ------------ | ------------ |------------ |
| SoundRender | 修改音色，弹奏乐器，弹奏速度  | @SoundRender后响应  |
| Max   | 生成格式一致的下一段乐谱  |  @Max后响应 |
| MusicWorker  |  生成电子简谱，可播放 |  上传文件后自动响应，分析音频 |
|  News-hunter |  爬取音乐相关新闻并生成海报 |  每隔1min触发，在music-news窗口中 |
## 快速开始



```python
cd ~/music_free
pip install -r requirements.txt

# 后端网络
openagents network start music &

# 前端
cd openagents/studio
npm start &

# 音乐代理
cd ../../music/agents
python llm_agent.py & 
python music_agent.py &
python sound_agent.py &

# 新闻代理
cd music_news/agents
python news_hunter.py &
```

演示效果(飞书链接)：
https://d94sx79yh3.feishu.cn/wiki/Fpqwwweq0iXiqYklubrc63wXnQe?from=from_copylink
