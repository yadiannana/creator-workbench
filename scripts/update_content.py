#!/usr/bin/env python3
"""
宝妈创作工作台 - 每日自动更新脚本
功能：
1. 抓取抖音热榜、微博热搜、B站热门、百度热搜、知乎热榜
2. 用DeepSeek AI改写成贴合"宝妈勇闯自媒体"赛道的内容
3. 生成10条选题灵感 + 10条热点二创文案
4. 推送到GitHub Gist
"""

import json
import os
import re
import sys
import time
import datetime
import urllib.parse
import requests
from bs4 import BeautifulSoup

# ============================================================
# 配置
# ============================================================
TODAY = datetime.date.today().strftime('%Y-%m-%d')
NOW = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

# DeepSeek AI 配置
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_API_URL = os.environ.get('AI_API_URL', 'https://api.deepseek.com/v1/chat/completions')

# Gist 配置
GIST_ID = os.environ.get('GIST_ID', '')
GH_TOKEN = os.environ.get('GH_PAT') or os.environ.get('GITHUB_TOKEN', '')

# 宝妈人设
PERSONA = """我的人设：
- 宝妈，想赚钱，努力活着，有正能量
- 每天文案配图：孩子户外/室内背影/侧面正面照片，少量母子合照
- 文案来源：人民日报金句、通透句库、抖音热搜、明星发言、热门歌曲
- 需要关联到：宝妈搞钱、女性成长、柴米油盐和自媒体
- 还没赚到钱，但赚钱欲望非常强烈（不要写已赚广告费等不实内容）
- 目标受众：25-40岁宝妈

文案格式要求：
- 标题要有钩子，要吸引要通透
- 原文金句保留3-4句，个人感悟写2-3句
- 合在一起做一个正文，放在图文上
- 图文下方可写延伸性正文：长的10句，短的5-6句
- 图片上方标题金句+解读感悟，总共不超过10句
- 每句字数12-16字左右
- 读着要有连贯性
- 站在25-40岁宝妈角度，写与她们息息相关的
- 通透、有力量、利他"""

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
}

# ============================================================
# 数据抓取
# ============================================================
def fetch_douyin_hot():
    """抓取抖音热榜"""
    try:
        url = 'https://www.douyin.com/aweme/v1/web/hot/search_list/'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('word_list', [])[:15]:
            items.append({
                'title': item.get('word', ''),
                'source': 'dy',
                'sourceLabel': '抖音热榜',
            })
        return items
    except Exception as e:
        print(f"  抖音热榜: {e}")
        return []

def fetch_weibo_hot():
    """抓取微博热搜"""
    try:
        url = 'https://weibo.com/ajax/side/hotSearch'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('realtime', [])[:15]:
            items.append({
                'title': item.get('note', ''),
                'source': 'weibo',
                'sourceLabel': '微博热搜',
            })
        return items
    except Exception as e:
        print(f"  微博热搜: {e}")
        return []

def fetch_bili_hot():
    """抓取B站热门"""
    try:
        url = 'https://api.bilibili.com/x/web-interface/search/square?keyword='
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('trending', {}).get('list', [])[:15]:
            items.append({
                'title': item.get('keyword', ''),
                'source': 'bili',
                'sourceLabel': 'B站热门',
            })
        return items
    except Exception as e:
        print(f"  B站热门: {e}")
        return []

def fetch_baidu_hot():
    """抓取百度热搜"""
    try:
        url = 'https://top.baidu.com/api/board?platform=wise&tab=realtime'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('cards', [{}])[0].get('content', [])[:15]:
            items.append({
                'title': item.get('word', ''),
                'source': 'baidu',
                'sourceLabel': '百度热搜',
            })
        return items
    except Exception as e:
        print(f"  百度热搜: {e}")
        return []

def fetch_zhihu_hot():
    """抓取知乎热榜"""
    try:
        url = 'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=15'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', [])[:15]:
            target = item.get('target', {})
            items.append({
                'title': target.get('title', ''),
                'source': 'zhihu',
                'sourceLabel': '知乎热榜',
            })
        return items
    except Exception as e:
        print(f"  知乎热榜: {e}")
        return []

def fetch_weibo_star_topics():
    """抓取微博明星话题/娱乐热搜（女性关注度高）"""
    try:
        url = 'https://weibo.com/ajax/side/hotSearch'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        # 娱乐/明星分类
        for item in data.get('data', {}).get('realtime', [])[:30]:
            category = item.get('category', '')
            label = item.get('label_name', '')
            note = item.get('note', '')
            # 筛选明星/娱乐相关
            if any(kw in note for kw in ['明星','演员','歌手','获奖','感言','说','回应',
                    '杨紫','张凌赫','孟子义','周星驰','徐良','赵露思','虞书欣',
                    '演唱会','舞台','伴舞','歌词','新歌','专辑','明星发言']):
                items.append({
                    'title': note,
                    'source': 'star',
                    'sourceLabel': '明星动态',
                })
        return items[:10]
    except Exception as e:
        print(f"  微博明星: {e}")
        return []

def fetch_netease_hot_songs():
    """抓取网易云音乐热歌榜（热门歌曲/伴舞相关）"""
    try:
        url = 'https://music.163.com/api/playlist/detail?id=3778678'  # 云音乐热歌榜
        resp = requests.get(url, headers={
            'User-Agent': HEADERS['User-Agent'],
            'Referer': 'https://music.163.com'
        }, timeout=10)
        data = resp.json()
        items = []
        tracks = data.get('result', {}).get('tracks', [])[:10]
        for track in tracks:
            name = track.get('name', '')
            artist = track.get('artists', [{}])[0].get('name', '')
            items.append({
                'title': f'《{name}》-{artist}',
                'source': 'song',
                'sourceLabel': '热门歌曲',
            })
        return items
    except Exception as e:
        print(f"  网易云热歌: {e}")
        return []

def fetch_bili_hot_topics():
    """抓取B站热门视频（娱乐/明星/舞蹈类）"""
    try:
        url = 'https://api.bilibili.com/x/web-interface/popular?ps=10&pn=1'
        resp = requests.get(url, headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get('data', {}).get('list', [])[:10]:
            title = item.get('title', '').replace('<em class="keyword">','').replace('</em>','')
            tname = item.get('tname', '')
            # 筛选女性关注的内容：明星/舞蹈/音乐/生活
            if tname in ('明星','舞蹈','音乐','生活','美妆','日常') or \
               any(kw in title for kw in ['明星','舞台','伴舞','歌曲','歌词','感言',
                   '杨紫','张凌赫','孟子义','周星驰','徐良','说','金句','通透']):
                items.append({
                    'title': title,
                    'source': 'bili',
                    'sourceLabel': 'B站热门',
                })
        return items
    except Exception as e:
        print(f"  B站热门视频: {e}")
        return []

def fetch_all_hot():
    """抓取所有热榜+明星动态+热门歌曲"""
    all_hot = []
    print("开始抓取热度内容...")
    sources = [
        ('抖音', fetch_douyin_hot),
        ('微博热搜', fetch_weibo_hot),
        ('微博明星', fetch_weibo_star_topics),
        ('B站热门', fetch_bili_hot),
        ('B站视频', fetch_bili_hot_topics),
        ('百度', fetch_baidu_hot),
        ('知乎', fetch_zhihu_hot),
        ('网易云热歌', fetch_netease_hot_songs),
    ]
    for name, func in sources:
        try:
            items = func()
            all_hot.extend(items)
            print(f"  {name}: {len(items)}条")
        except Exception as e:
            print(f"  {name}: 异常 {e}")
    print(f"  共抓取 {len(all_hot)} 条")
    return all_hot

# ============================================================
# DeepSeek AI 改写
# ============================================================
def call_deepseek(prompt, system_prompt=''):
    """调用DeepSeek API"""
    if not AI_API_KEY:
        print("  [AI] 未配置AI_API_KEY，跳过AI改写")
        return None

    headers = {
        'Authorization': f'Bearer {AI_API_KEY}',
        'Content-Type': 'application/json'
    }
    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    messages.append({'role': 'user', 'content': prompt})

    payload = {
        'model': 'deepseek-chat',
        'messages': messages,
        'max_tokens': 800,
        'temperature': 0.8,
        'stream': False
    }

    try:
        print(f"  [AI] 调用DeepSeek API...")
        resp = requests.post(AI_API_URL, json=payload, headers=headers, timeout=60)
        if resp.status_code != 200:
            print(f"  [AI] API返回 {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        content = data['choices'][0]['message']['content'].strip()
        print(f"  [AI] 改写成功，长度{len(content)}字")
        return content
    except Exception as e:
        print(f"  [AI] 调用失败: {e}")
        return None

def parse_ai_json(text):
    """尝试从AI回复中解析JSON"""
    if not text:
        return None
    # 去掉markdown代码块
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'^```\s*', '', text)
    text = text.strip().rstrip('`').strip()

    # 直接解析
    try:
        return json.loads(text)
    except:
        pass

    # 尝试提取JSON数组（从第一个[到最后一个]）
    arr_start = text.find('[')
    arr_end = text.rfind(']')
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        json_str = text[arr_start:arr_end+1]
        try:
            return json.loads(json_str)
        except:
            pass
        # 尝试修复常见的JSON问题：换行符在字符串值里未转义
        # 逐个解析每个对象
        try:
            # 用正则提取每个JSON对象（这段保留但不使用，作为备选）
            # objects = re.findall(r'\{[^{}]+\}', json_str)
            pass
        except:
            pass

    # 尝试提取JSON对象
    obj_start = text.find('{')
    obj_end = text.rfind('}')
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        json_str = text[obj_start:obj_end+1]
        try:
            return json.loads(json_str)
        except:
            pass

    # 最后尝试：逐行清洗，把字符串值内的裸换行替换为\n
    try:
        cleaned = text
        # 在双引号内的换行替换为\n
        def escape_newlines_in_strings(s):
            result = []
            in_string = False
            escaped = False
            for char in s:
                if escaped:
                    result.append(char)
                    escaped = False
                    continue
                if char == '\\':
                    result.append(char)
                    escaped = True
                    continue
                if char == '"':
                    in_string = not in_string
                    result.append(char)
                    continue
                if char == '\n' and in_string:
                    result.append('\\n')
                    continue
                if char == '\r' and in_string:
                    continue
                result.append(char)
            return ''.join(result)

        cleaned = escape_newlines_in_strings(text)
        # 再尝试解析
        arr_start = cleaned.find('[')
        arr_end = cleaned.rfind(']')
        if arr_start != -1 and arr_end != -1:
            return json.loads(cleaned[arr_start:arr_end+1])
        obj_start = cleaned.find('{')
        obj_end = cleaned.rfind('}')
        if obj_start != -1 and obj_end != -1:
            return json.loads(cleaned[obj_start:obj_end+1])
    except:
        pass

    return None

# ============================================================
# 生成选题灵感（AI改写）
# ============================================================
def generate_topics_ai(hot_items):
    """用AI生成10条选题灵感"""
    # 热榜关键词摘要
    hot_summary = ""
    if hot_items:
        top5 = hot_items[:8]
        hot_summary = "当天热榜：\n" + "\n".join([f"- {h['sourceLabel']}: {h['title']}" for h in top5])

    prompt = f"""{PERSONA}

根据以上人设和当天热榜，帮我生成10条选题灵感。

要求：
1. 每条选题要和"宝妈勇闯自媒体"关联
2. 标题要有钩子，吸引25-40岁宝妈
3. 标签2-3个
4. 说明要写清楚关联点（为什么这个选题适合宝妈自媒体）

{hot_summary}

请严格按JSON数组格式返回，不要返回其他内容：
[
  {{"title":"标题（15-25字）","tags":["标签1","标签2"],"desc":"说明（30-50字，写关联点）"}}
]

共10条。"""

    result = call_deepseek(prompt)
    if result:
        parsed = parse_ai_json(result)
        if parsed and isinstance(parsed, list) and len(parsed) >= 5:
            print(f"  AI生成 {len(parsed)} 条选题")
            # 补齐10条
            while len(parsed) < 10:
                parsed.append(parsed[len(parsed) % len(parsed)])
            return parsed[:10]

    # 降级：模板
    print("  使用模板选题")
    return get_fallback_topics()

def get_fallback_topics():
    """模板选题（AI失败时用）"""
    return [
        {'title':'宝妈带娃崩溃瞬间，你中了几条？','tags':['宝妈日常','共鸣'],'desc':'盘点带娃最崩溃的5个瞬间，引发同频宝妈共鸣。关联：每个崩溃背后都是妈妈的爱。'},
        {'title':'孩子睡着后，我偷偷做了这件事','tags':['宝妈搞钱','副业'],'desc':'夜深人静孩子睡了，宝妈副业搞钱的时间到了。关联：努力活着不只是口号。'},
        {'title':'从手心向上到手心向下，我用了多久','tags':['女性成长','经济独立'],'desc':'记录从伸手要钱到自己赚钱的心理变化。关联：赚钱欲望是最好的动力。'},
        {'title':'今天孩子说了一句话，我破防了','tags':['亲子','金句'],'desc':'孩子无意间一句话，让努力搞钱的妈妈红了眼眶。关联：娃是我的底气。'},
        {'title':'月薪3千和副业过万，我选了后者','tags':['宝妈副业','自媒体'],'desc':'记录做自媒体心路历程，不吹嘘收入，只谈真实感受。关联：还没赚到但欲望很强。'},
        {'title':'那些带娃时想放弃的瞬间','tags':['宝妈心态','正能量'],'desc':'带娃疲惫想放弃时，是什么让我坚持。关联：努力活着的正能量。'},
        {'title':'孩子你慢点长大，妈妈还在努力','tags':['亲子','成长'],'desc':'写给孩子的信，妈妈在努力成为更好的人。关联：娃是前进的动力。'},
        {'title':'全职妈妈的一天，比上班还累','tags':['宝妈日常','共鸣'],'desc':'从早到晚真实记录，引发宝妈群体共鸣。关联：柴米油盐里的坚强。'},
        {'title':'我为什么开始做自媒体','tags':['宝妈创业','初心'],'desc':'回顾做自媒体的初心，赚钱+成长+给孩子更好生活。关联：真实不装。'},
        {'title':'当了妈才知道的10件事','tags':['宝妈感悟','通透'],'desc':'当妈后的感悟金句，每句都戳心。关联：用通透的视角看宝妈生活。'},
    ]

# ============================================================
# 钩子知识库（对标抖音/小红书宝妈赛道）
# ============================================================
HOOK_TEMPLATES = """宝妈赛道7种爆款钩子模板（10-15字一句话）：
1. 痛点暴击式："带娃带到崩溃的妈妈，听这段话"
2. 反常识颠覆式："越省钱反而越穷的真相，太现实"
3. 提问共鸣式："你有没有一瞬间，突然觉得特别累？"
4. 对比反差式："以前我讨好所有人，现在只讨好自己"
5. 警告提醒式："别再乱发朋友圈了，真的很掉价"
6. 故事开头式："昨天一条私信，看完特别心疼"
7. 圈层召唤式："想赚钱的宝妈，一定要看完这段"

万能钩子公式：
- 同样是宝妈，为什么她XX你却XX
- 带娃XX天我才明白，XX才是真相
- 如果你也是XX的妈妈，请听完
- 月薪X千的宝妈，千万别做这X件事
- 我花X年才懂的道理，今天告诉你

钩子要求：
- 10-15字一句话
- 第一秒点名"宝妈/妈妈/带娃"精准锚定人群
- 必须有强情绪词：崩溃、心酸、熬、想哭、后悔、惊醒
- 配图+钩子咬合：孩子背影照配反差钩子效果最好"""

# ============================================================
# 生成热点二创（AI改写，含钩子）
# ============================================================
def generate_hot_items_ai(hot_items):
    """用AI生成10条热点二创内容，每条含钩子"""

    # 按类型分组热度内容，确保来源多样化
    # 3条热搜 + 3条明星动态 + 2条歌曲 + 2条通透金句
    hot_sources = [h for h in hot_items if h['source'] in ('dy','weibo','baidu','zhihu')][:3]
    star_sources = [h for h in hot_items if h['sourceLabel'] in ('明星动态','明星发言')][:3]
    song_sources = [h for h in hot_items if h['sourceLabel'] in ('热门歌曲',)][:2]

    # 补充固定类型模板
    type_templates = [
        {'source':'star','sourceLabel':'明星发言','title':'杨紫获奖感言：感谢每一个没有放弃的自己'},
        {'source':'star','sourceLabel':'明星发言','title':'张凌赫：努力的人终会被看见'},
        {'source':'star','sourceLabel':'明星发言','title':'孟子义谈女性独立：不需要依附任何人'},
        {'source':'star','sourceLabel':'明星发言','title':'周星驰：做人如果没有梦想，跟咸鱼有什么区别'},
        {'source':'song','sourceLabel':'热门歌曲','title':'徐良歌曲伴舞火了，歌词戳中宝妈心事'},
        {'source':'song','sourceLabel':'热门歌曲','title':'《如愿》——你心我生长的方向'},
        {'source':'news','sourceLabel':'通透句库','title':'人民日报金句：所有的努力都不会被辜负'},
        {'source':'news','sourceLabel':'通透句库','title':'通透句库：人生没有白走的路，每一步都算数'},
    ]

    all_sources = []
    # 优先用实际抓取的内容
    all_sources.extend(hot_sources)
    all_sources.extend(star_sources)
    all_sources.extend(song_sources)

    # 用模板补齐到10条
    for t in type_templates:
        if len(all_sources) >= 10:
            break
        all_sources.append(t)

    while len(all_sources) < 10:
        all_sources.append(type_templates[len(all_sources) % len(type_templates)])

    # 构建热度摘要给AI
    hot_summary = "\n".join([f"{i+1}. [{s['sourceLabel']}] {s['title']}" for i, s in enumerate(all_sources[:10])])

    # 一次性让AI生成所有10条（分2批，每批5条，保证质量）
    items = []

    for batch in range(2):
        batch_sources = all_sources[batch*5:(batch+1)*5]
        batch_summary = "\n".join([f"{i+1}. [{s['sourceLabel']}] {s['title']}" for i, s in enumerate(batch_sources)])

        print(f"  生成第{batch*5+1}-{batch*5+5}条二创...")
        prompt = f"""{PERSONA}

{HOOK_TEMPLATES}

为以下5条热度内容分别写二创文案：

{batch_summary}

每条要求：
1. hook: 钩子，10-15字一句话，用上面的钩子模板，必须点名宝妈/妈妈/带娃
2. angle: 改编角度，怎么关联到宝妈搞钱、女性成长、柴米油盐和自媒体（30-50字）
3. copyTitle: 文案标题（通透、有钩子感）
4. copyOriginal: 保留来源的3-4句精华原句
5. copyText: 完整二创文案
   - 金句3-4句 + 个人感悟2-3句，合为一个正文
   - 每句12-16字，读着要有连贯性
   - 不写已赚广告费等不实内容，赚钱欲望强烈但还没赚到
   - 延伸正文5-10句，放在图文下方
6. 整体风格：通透、有力量、利他

请严格按JSON数组格式返回5条，不要返回其他内容：
[
  {{"hook":"10-15字钩子","angle":"改编角度","copyTitle":"标题","copyOriginal":"原句","copyText":"完整文案（用\\n换行）"}}
]"""

        result = call_deepseek(prompt)
        if result:
            # 保存AI原始返回用于调试
            os.makedirs('data', exist_ok=True)
            with open(f'data/ai_raw_batch{batch+1}.txt', 'w', encoding='utf-8') as f:
                f.write(result)

            parsed = parse_ai_json(result)
            if parsed and isinstance(parsed, list):
                for i, p in enumerate(parsed):
                    if 'copyText' in p:
                        src = batch_sources[i] if i < len(batch_sources) else batch_sources[0]
                        items.append({
                            'source': src.get('source', 'news'),
                            'sourceLabel': src.get('sourceLabel', '热点'),
                            'title': src.get('title', ''),
                            'hook': p.get('hook', ''),
                            'angle': p.get('angle', ''),
                            'copyTitle': p.get('copyTitle', ''),
                            'copyOriginal': p.get('copyOriginal', ''),
                            'copyText': p.get('copyText', '')
                        })
                print(f"  第{batch+1}批AI生成 {len(parsed)} 条")
                continue
            else:
                print(f"  第{batch+1}批JSON解析失败，使用模板")
                print(f"  AI返回前200字: {repr(result[:200])}")
                # 尝试找到失败原因
                try:
                    json.loads(result.strip().rstrip('`'))
                except json.JSONDecodeError as e:
                    print(f"  JSON错误: {e}")
                    print(f"  错误位置附近: {repr(result[max(0,e.pos-30):e.pos+30])}")

        # AI失败，用模板补充
        for i, src in enumerate(batch_sources):
            if len(items) < (batch+1)*5:
                items.append(get_fallback_hot_item(batch*5+i, src))

    # 确保正好10条
    while len(items) < 10:
        idx = len(items)
        src = all_sources[idx % len(all_sources)]
        items.append(get_fallback_hot_item(idx, src))

    # 给模板项也加hook
    for item in items:
        if not item.get('hook'):
            item['hook'] = generate_hook_fallback(item.get('title', ''))

    return items[:10]

def generate_hook_fallback(title):
    """模板钩子（AI失败时用）"""
    hooks = [
        '带娃崩溃的妈妈，看完这段释怀了',
        '想赚钱的宝妈，千万别错过这条',
        '同样是宝妈，为什么她那么通透',
        '如果你也是累到想哭的妈妈，请听完',
        '月薪三千的宝妈，我劝你看看这个',
        '当妈后我才明白的真相，太戳心',
        '别再emo了，带娃的妈妈听我说',
        '看完这条的宝妈，都去搞钱了',
        '我花三年才懂的道理，今天告诉你',
        '带娃最累的那天，我想通了这件事',
    ]
    return hooks[hash(title) % len(hooks)]

def get_fallback_hot_item(i, src):
    """模板二创（AI失败时用）"""
    templates = [
        {'angle':'关联宝妈日常：把明星的话翻译成宝妈视角。','copyTitle':'当妈后我懂了','copyOriginal':src['title'],'copyText':'当妈这件事\n没有彩排\n每天都是现场直播\n\n没有NG的机会\n孩子哭了你得接着\n累了不能替班\n\n但你看 我还在努力\n不是因为不累\n是因为怀里这个小人儿\n值得我拼尽全力'},
        {'angle':'关联宝妈搞钱：宝妈就是生活里的孤勇者。','copyTitle':'谁说带娃不算英雄','copyOriginal':src['title'],'copyText':'谁说站在光里的才算英雄\n我每天在厨房客厅战斗\n\n围裙是我的披风\n奶瓶是我的武器\n孩子的笑脸是我的勋章\n\n赚钱的欲望推着我往前走\n不是贪心\n是想给孩子更好的生活'},
        {'angle':'不吹嘘收入，谈真实感受。','copyTitle':'我先说真话','copyOriginal':src['title'],'copyText':'又看到别人月入过万了\n我当妈到现在\n自媒体还没赚到一分钱\n\n但我不想说假话\n赚钱的欲望很强烈\n强烈到每天孩子睡了\n我还坐在手机前\n\n也许明天就赚到第一块钱了\n也许还要很久\n但妈妈在努力\n这件事本身就很了不起'},
        {'angle':'关联宝妈日常变化，用通透金句串联。','copyTitle':'当妈后 我变了','copyOriginal':src['title'],'copyText':'当妈后\n我学会了边吃饭边抱娃\n学会了睁眼就干活\n学会了把哭咽回去\n\n但我也学会了\n在缝隙里给自己找光\n在疲惫里给自己找希望\n在柴米油盐里\n给自己留一个赚钱的梦'},
        {'angle':'关联亲子成长和搞钱动力。','copyTitle':'我心生长的方向','copyOriginal':src['title'],'copyText':'你是我心生长的方向\n也是我拼命的理由\n\n我想给你更好的生活\n不是溺爱\n是让你有底气去闯\n\n所以我在努力 在赚钱\n在自媒体这条路上\n跌跌撞撞\n\n也许慢了点\n但方向从来没错'},
        {'angle':'关联宝妈搞钱路，还没赚到但相信努力。','copyTitle':'努力不会被辜负','copyOriginal':src['title'],'copyText':'所有的努力都不会被辜负\n这句话我贴在手机壁纸上\n\n当妈后我做了很多\n没人看见的事\n\n每一个深夜的坚持\n每一次想哭又忍住\n还没赚到钱 但我相信\n走过的路 都算数'},
        {'angle':'关联宝妈搞钱和自媒体。','copyTitle':'一百种可能','copyOriginal':src['title'],'copyText':'全职妈妈\n不只有一种活法\n\n我见过带娃做自媒体的\n我见过孩子睡了写文案的\n我见过一手奶瓶一手手机的\n\n我不是例外\n我是其中之一\n在柴米油盐里\n给自己拼一个可能'},
        {'angle':'关联宝妈逆风前行的状态。','copyTitle':'逆着风 走','copyOriginal':src['title'],'copyText':'逆着风 走\n当妈后我常这样\n\n收入不稳 孩子要带\n家里事多 外面要拼\n每一步都是逆风\n\n但你看\n逆风走的妈妈\n走得慢 但走得稳\n走得累 但走得真'},
        {'angle':'关联宝妈搞钱和女性成长。','copyTitle':'被低估的力量','copyOriginal':src['title'],'copyText':'女性的力量被低估了\n我信\n\n因为当妈后我发现\n我能一边抱娃一边回消息\n我能一边做饭一边想选题\n我能在崩溃后第二天\n笑着继续\n\n这力量没人标价\n但我知道 它很值钱'},
        {'angle':'关联宝妈坚韧和搞钱决心。','copyTitle':'真正的坚强','copyOriginal':src['title'],'copyText':'当了妈才知道坚强\n我当了妈才知道\n坚强是哭着也要把奶温好\n坚强是累瘫了也要检查作业\n坚强是想放弃时看一眼娃\n又咬牙撑过去了\n\n你看 当妈这件事\n让我们都变成了\n自己以前最佩服的那种人'},
    ]
    t = templates[i % len(templates)]
    t['source'] = src.get('source', 'news')
    t['sourceLabel'] = src.get('sourceLabel', '热点')
    t['title'] = src.get('title', t.get('title',''))
    return t

# ============================================================
# 推送到Gist
# ============================================================
def push_to_gist(data):
    """推送数据到GitHub Gist"""
    if not GIST_ID:
        print("  未配置GIST_ID，跳过推送")
        return False
    if not GH_TOKEN:
        print("  未配置GH_TOKEN，跳过推送")
        return False

    url = f'https://api.github.com/gists/{GIST_ID}'
    headers = {
        'Authorization': f'token {GH_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    content = json.dumps(data, ensure_ascii=False, indent=2)
    payload = {
        'files': {
            'creator-data.json': {
                'content': content
            }
        }
    }

    try:
        print(f"  推送到Gist {GIST_ID[:8]}...")
        resp = requests.patch(url, json=payload, headers=headers, timeout=30)
        if resp.status_code in (200, 201):
            print("  Gist推送成功！")
            return True
        else:
            print(f"  Gist推送失败: {resp.status_code} {resp.text[:100]}")
            return False
    except Exception as e:
        print(f"  Gist推送异常: {e}")
        return False

# ============================================================
# 主函数
# ============================================================
def main():
    print(f"=== 宝妈创作工作台 自动更新 ===")
    print(f"时间: {NOW}")
    print(f"AI: {'DeepSeek已配置' if AI_API_KEY else '未配置（用模板）'}")
    print(f"Gist: {'已配置' if GIST_ID else '未配置'}")
    print()

    # 1. 抓取热榜
    hot_items = fetch_all_hot()

    # 2. 生成选题灵感
    print("\n生成选题灵感...")
    topics = generate_topics_ai(hot_items)
    print(f"  完成: {len(topics)} 条选题")

    # 3. 生成热点二创
    print("\n生成热点二创...")
    hot_data = generate_hot_items_ai(hot_items)
    print(f"  完成: {len(hot_data)} 条二创")

    # 4. 组装
    result = {
        'date': TODAY,
        'updateTime': NOW,
        'topics': {
            'date': TODAY,
            'updateTime': NOW,
            'topics': topics
        },
        'hot': {
            'date': TODAY,
            'updateTime': NOW,
            'items': hot_data
        }
    }

    # 5. 写入本地文件
    os.makedirs('data', exist_ok=True)
    with open('data/creator-data.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n本地数据已写入 data/creator-data.json")

    # 6. 推送到Gist
    print("\n推送到Gist...")
    push_to_gist(result)

    print(f"\n=== 更新完成 {NOW} ===")

if __name__ == '__main__':
    main()
