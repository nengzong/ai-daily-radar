# AI Daily Radar — 信息源清单(43 个)

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

## 筛选标准(AI 从原始信息里挑什么)

- **行业动向**:AI 在建筑、园区、工厂、能源、设施管理(FM)等空间/资产运营场景的落地信号——新产品发布、标杆项目、政策与市场动态
- **技术与案例**:Agent、世界模型、AIoT、大模型企业级落地的技术进展与实践案例,优先挑有可量化效果、有明确场景的
- **产品灵感**:交互、定位、增长玩法上有借鉴价值的新产品
- 与公司方向(工程物理世界 AI:楼宇/园区/工厂运营、设施管理 FM、企业服务、Agent/BOT)相关的信号**优先级最高**
- 日报会推送到公司钉钉群,读者是同事和领导。所有内容都从「对公司业务、产品和技术选型有什么参考价值」的视角来写,**不要出现"值得做"、"赚钱"、"副业"、"个人变现"之类的措辞**
