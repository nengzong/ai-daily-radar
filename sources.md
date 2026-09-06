# AI Daily Radar — 信息源清单(45 个)

> 每天早上定时任务会逐条扫描本清单。想增删信息源,直接编辑本文件即可,无需改定时任务。
> 抓取方式:优先用 WebFetch 直接抓 URL(标注 RSS 的地址是 XML 源,比抓首页稳定);抓不到(反爬/需登录)就用 WebSearch 搜当日相关内容兜底。
> 海外源(C/D/E/F 四组)是日报的主体来源之一,**每期至少 40% 条目要来自海外源**,不能只挑国内中文内容。

## A. App Store 新应用/榜单异动(5 个区)

Apple 官方榜单 JSON(免登录、稳定),重点看**新进榜**和**排名飙升**的 AI/效率类应用:

1. 🇨🇳 中国区:https://rss.applemarketingtools.com/api/v2/cn/apps/top-free/50/apps.json
2. 🇺🇸 美国区:https://rss.applemarketingtools.com/api/v2/us/apps/top-free/50/apps.json
3. 🇯🇵 日本区:https://rss.applemarketingtools.com/api/v2/jp/apps/top-free/50/apps.json
4. 🇬🇧 英国区:https://rss.applemarketingtools.com/api/v2/gb/apps/top-free/50/apps.json
5. 🇭🇰 香港区:https://rss.applemarketingtools.com/api/v2/hk/apps/top-free/50/apps.json

> 对比 `reports/appstore-snapshot.json`(每次运行后更新)找出新进榜应用。

## B. 国内社区 & 媒体(10 个)

6. 即刻「AI探索站」圈子 — 用 WebSearch 搜 `site:okjike.com AI探索站` 当日热帖,或搜「即刻 AI探索站 热门」
7. 即刻「AI产品经理」圈子 — 同上方式
8. 即刻「一人公司/出海」相关圈子(独立开发、出海人的日常)— 同上方式
9. 36氪 AI 频道:https://36kr.com/information/AI/
10. 少数派首页:https://sspai.com/
11. V2EX 分享创造:https://www.v2ex.com/go/create (顺带看 https://www.v2ex.com/go/ai)
12. 量子位:https://www.qbitai.com/
13. 机器之心:https://www.jiqizhixin.com/
14. 虎嗅 AI:https://www.huxiu.com/channel/107.html (抓不到就 WebSearch「虎嗅 AI 今日」)
15. AI产品榜:https://aicpb.com/ (看新上榜产品)

## C. 海外社区(4 个,内容需翻译成中文)

16. GitHub Trending:https://github.com/trending (daily,重点 AI/工具类新仓库)
17. Product Hunt:https://www.producthunt.com/ (当日 Top 产品)
18. Hacker News:https://news.ycombinator.com/ (首页 + Show HN,重点 AI/独立开发者项目)
19. Reddit 独立开发圈:r/SideProject、r/indiehackers、r/ArtificialInteligence — 抓 https://www.reddit.com/r/SideProject/top/?t=day 等,抓不到就 WebSearch 兜底

## D. 顶级 AI 实验室 & 平台官方(6 个,一手信息)

20. OpenAI News(RSS):https://openai.com/news/rss.xml
21. Anthropic News:https://www.anthropic.com/news
22. Google DeepMind Blog(RSS):https://deepmind.google/blog/rss.xml
23. NVIDIA Blog(RSS):https://blogs.nvidia.com/feed/ (重点 Omniverse、数字孪生、工业/机器人 AI、物理 AI)
24. Microsoft AI:https://blogs.microsoft.com/ai/ (反爬,直接 WebSearch「Microsoft AI blog」当日内容)
25. Hugging Face Daily Papers:https://huggingface.co/papers (每日热门论文,只挑 Agent/世界模型/多模态/时序等与公司相关的)

## E. 顶级科技媒体 & 通讯(11 个,内容需翻译成中文)

26. TechCrunch AI(RSS):https://techcrunch.com/category/artificial-intelligence/feed/
27. The Verge AI(RSS):https://www.theverge.com/rss/ai-artificial-intelligence/index.xml
28. MIT Technology Review AI(RSS):https://www.technologyreview.com/topic/artificial-intelligence/feed
29. VentureBeat AI(RSS):https://venturebeat.com/category/ai/feed/
30. The Information AI:https://www.theinformation.com/ (付费墙,用 WebSearch「The Information AI」看当日标题)
31. The Batch(deeplearning.ai 周报):https://www.deeplearning.ai/the-batch/
32. **QMReader 聚合源(一次抓取覆盖多个海外博主/通讯,自带中文译标题)**:https://rss.qiaomu.ai/api/entries
    - 返回最近 400 条 JSON,字段 `sourceId` / `titleZh` / `summaryZh` / `link` / `published`。**只保留以下 `sourceId`**,其余忽略:
      `simonwillison`(Simon Willison,LLM 工具圈最一手)、`importai`(Jack Clark 周报)、`interconnects`(Nathan Lambert,开源模型)、`oneusefulthing`(Ethan Mollick,企业用 AI)、`latentspace`(AI 工程师播客)、`tldrai` / `bensbites` / `superhuman_ai`(英文 AI 日报)、`chinai`(海外视角看中国 AI)、`construction-physics`(建筑业生产率与工程物理,与公司方向直接相关)、`huggingface`(论文)
    - 只取 `published` 在最近 48 小时内的条目。
    - 这是第三方个人站,挂了就回退到下面各源的原站 RSS:
33. Simon Willison(RSS 兜底):https://simonwillison.net/atom/everything/
34. Import AI(RSS 兜底):https://importai.substack.com/feed
35. One Useful Thing(RSS 兜底):https://www.oneusefulthing.org/feed
36. Construction Physics(RSS 兜底):https://www.construction-physics.com/feed

> 33-36 仅在 32 抓取失败时才抓;32 正常时跳过,不重复计入源覆盖。

## F. 垂直行业:楼宇 / 设施管理 / 能源 / 工业 AI(7 个,🏭 行业动向优先从这组取材)

37. FacilitiesNet(设施管理,RSS):https://www.facilitiesnet.com/rss/facilitiesnetarticles.aspx (楼宇自控专栏:https://www.facilitiesnet.com/rss/section/Building-Automation--159)
38. Smart Buildings Magazine:https://www.smartbuildingsmagazine.com/
39. IFMA News(国际设施管理协会):https://www.ifma.org/news/
40. Utility Dive(能源/电网,RSS):https://www.utilitydive.com/feeds/news/ (只挑 AI、数据中心、需求响应、楼宇能效相关)
41. AEC Magazine(建筑/工程/施工数字化,RSS):https://aecmag.com/feed/
42. IoT World Today(AIoT/工业物联网):https://www.iotworldtoday.com/
43. 厂商新闻室(合并为一条,用 WebSearch 搜当日/本周新闻):Siemens Building X(https://press.siemens.com/global/en)、Schneider Electric EcoStruxure、Johnson Controls OpenBlue(https://www.johnsoncontrols.com/media-center/news)、Honeywell Forge(https://www.honeywell.com/us/en/press)、Bentley Systems、Memoori(智能楼宇研究,反爬)——搜 `<厂商名> AI building` 近 7 天内容,只挑有 AI 落地实质的发布

## G. 设计与体验(1 个,🎨 设计动态栏目专用)

44. **DEX 周刊**(中文,产品/设计/前端方向的每周精选,自带中文点评):
    - 目录源(Atom):https://quaily.com/dingyi/feed/atom —— 只给标题和链接,**摘要字段是空的**,要正文必须再抓一次期刊页
    - 期刊正文:https://quaily.com/dingyi/p/<期号>(公开可读,无付费墙),栏目为「上周设计新闻 / Resources / Cases / Articles」
    - **周更**(通常周一、周二发),所以大部分工作日没有新内容 —— 抓取规则见下,不要重复取材同一期

### G 组抓取规则(避免每天重复推同一期)

1. 抓 Atom 目录,取**最新一期**的 `published` 时间、标题和链接。
2. `published` 距今超过 7 天 → 判定本周尚未更新,**跳过整组**,🎨 栏目不出现。
3. 在仓库里查这期是否已经推过:`grep -rl "quaily.com/dingyi/p/<期号>" reports/`。有命中 → 说明前几天的日报已经取过材,**跳过整组**。
4. 都通过了才抓期刊正文,按下面的口径挑 **1-3 条**。**这期没有一条符合口径 → 照样整组跳过**,不要为了把栏目填满硬凑——🎨 是「有才发」的栏目,不是每天必占的版面。
5. 每条**优先给条目本身的原始链接**(工具官网、文章原文、作品集地址),并在末尾注明 `via DEX 周刊 #<期号>`;实在拿不到原始链接才退回用期刊页链接。
6. 🎨 栏目的开头必须写一行 `> 本期来源:[DEX 周刊 #<期号>](https://quaily.com/dingyi/p/<期号>)` —— **第 3 步的去重就是靠这行**,漏了它明天会重复推同一期。
7. G 组条目**单独计数**:不计入「8-15 条」总数,也不计入海外条目占比的分子分母。

## H. X(Twitter)实践圈(1 个,🤖 技术与案例 / 💡 产品灵感 的一手补充)

45. **SoPilot 热帖 RSS**(中文 X 圈当日爆帖,免登录、无付费墙):https://sopilot.net/rss/hottweets
    - 标准 RSS 2.0,约 50 条/天。`<title>` 是「作者名 (@handle)」,`<pubDate>` 是 GMT;
      `<description>` 里是推文正文 + 互动数据 + 一行 `原推链接: https://x.com/<handle>/status/<id>`
    - **链接必须给 `原推链接:` 后面那个 x.com 地址**,不要给 `<link>` 里的 sopilot.net 聚合页
    - 它补的是 D、E 两组补不上的洞:那两组是官方发布和媒体报道,这里是**一线开发者的实测**
      ——模型在真实工程场景里到底行不行、踩了哪些坑、怎么绕过去。这类内容在别的源里基本看不到

### H 组抓取规则(这个源噪音大,规则比别处严)

这个源是**按爆火概率排序**的,不是按内容质量排序的。2026-09-06 实测当日 51 条里只有十几条
与我们有关,其余是房产宏观、币圈、社会话题、情绪吐槽和未证实的模型八卦。所以:

1. 只取 `pubDate` 在最近 **24 小时**内的条目。
2. **热度不是入选理由。** `预测爆火概率`、`预测浏览量` 这些字段一律无视,只看内容本身合不合口径。
3. **直接丢弃**这几类,不要犹豫:
   - 房产、宏观经济、城投债、股市——与日报口径无关
   - 币圈、DEX、meme、NFT、空投——同上
   - 社会话题、时政、地域争论、个人恩怨对线
   - 纯情绪吐槽和段子(「退钱」「气死我了」这类)
   - **未证实的「内部爆料」「突发」「知情人士称」**——日报进公司群,传闻会直接损伤可信度。
     同一件事若 E 组媒体也报了,用 E 组那版,不用这里的
   - 薅额度、省 token、绕限制一类的使用技巧——对公司的技术选型没有参考价值
4. **可以取**的是下面这几类,且必须**有实测、有数据或有可复现的方法**:
   - 3D / WebGL / Three.js / Blender / 数字孪生 的生成与呈现——直接对应楼宇与园区的三维场景
   - Agent 编排与工程化——任务拆解、多 Agent 分工、执行过程的可审计与证据链
   - 大模型在真实工程场景里的实测对比——有具体场景、有量化结论的那种
   - 企业级落地案例——标书、工单、知识库、流程自动化等 B 端场景
   - 有明确数据的榜单与评测结果
5. 每天**最多取 2 条**;一条都不合格就整组跳过,不要硬凑。
6. H 组条目**计入**「8-15 条」总数,但**不计入海外占比的分子分母**——它是中文内容,
   和 40% 那条规则要解决的问题(不能只挑国内中文内容)无关。

### 同批评估过、但没有采用的站点

2026-09-06 从一条「每天 10 分钟看完全网热点」的推荐里逐个验证,6 个站只有 SoPilot 通过。
记在这里,免得以后再花一次力气:

| 站点 | 没采用的原因 |
|---|---|
| NewsNow(newsnow.busiyi.world) | 首页和 `/api/s` 都返回 403,定时任务的 WebFetch 拿不到;且它覆盖的知乎/微博/B站/虎扑是消费级热点,其中唯一对口的 V2EX 我们已在 B 组直连 |
| 今日热榜(tophub.today) | 403 抓不到;且它科技版聚合的正是 GitHub Trending / Product Hunt / Hacker News——这三个 C 组已经直连,二手聚合只会更慢更差 |
| REBANG(top.open2hub.com) | 抖音/微博/百度/贴吧/快手/梨视频,**没有科技版块**,也没有 API 或 RSS |
| 英为财情(investing.com) | 全球行情与财经数据,和「AI 情报」的口径无关 |
| 萝卜投研(luobo.cn) | 股票投研平台,需登录,面向投资决策——它本身可以当成「AI 产品」来观察,但不是信息源 |

## 筛选标准(AI 从原始信息里挑什么)

- **行业动向**:AI 在建筑、园区、工厂、能源、设施管理(FM)等空间/资产运营场景的落地信号——新产品发布、标杆项目、政策与市场动态
- **技术与案例**:Agent、世界模型、AIoT、大模型企业级落地的技术进展与实践案例,优先挑有可量化效果、有明确场景的
- **产品灵感**:交互、定位、增长玩法上有借鉴价值的新产品
- **设计动态**(G 组):设计/前端圈里**对我们做的东西有迁移价值**的动向。合格的例子:
  - B 端复杂系统的界面与信息架构 —— 控制台、工单、报表、大体量表格与表单
  - 数据可视化与监控大屏 —— 时序曲线、指标卡、告警态、暗色主题下的图表可读性
  - 3D / WebGL / Three.js / 数字孪生 的呈现与交互 —— 直接对应楼宇与园区的三维模型场景
  - AI 产品的交互范式 —— 对话式界面、Agent 操作过程的可见与可控、AI 生成结果的确认与可解释
  - 设计工程与设计系统 —— 设计稿到代码的协同、组件库治理、AI 生成 UI 的质量把控(Figma / Code Connect / design skills 一类)
  - 现场作业类移动端交互 —— 巡检、报修、扫码等一线场景
  不合格的例子(直接跳过):个人作品集炫技、纯插画与视觉风格、品牌 logo 改版八卦、与企业级软件无关的营销站动效 —— 除非它给出了可复用的方法论
- 与公司方向(工程物理世界 AI:楼宇/园区/工厂运营、设施管理 FM、企业服务、Agent/BOT)相关的信号**优先级最高**
- 日报会推送到公司钉钉群,读者是同事和领导。所有内容都从「对公司业务、产品和技术选型有什么参考价值」的视角来写,**不要出现"值得做"、"赚钱"、"副业"、"个人变现"之类的措辞**
