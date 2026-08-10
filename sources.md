# AI Daily Radar — 信息源清单(19 个)

> 每天早上定时任务会逐条扫描本清单。想增删信息源,直接编辑本文件即可,无需改定时任务。
> 抓取方式:优先用 WebFetch 直接抓 URL;抓不到(反爬/需登录)就用 WebSearch 搜当日相关内容兜底。

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

## 筛选标准(AI 从原始信息里挑什么)

- **值得做的机会**:需求真实、门槛不高、大厂看不上或还没做的缝隙
- **赚钱案例**:有明确收入数字/商业模式的独立产品、出海案例
- **产品灵感**:交互、定位、增长玩法上有借鉴价值的新产品
- 与楼宇/设施管理(FM)、企业服务、Agent/BOT 方向相关的信号**优先级最高**
