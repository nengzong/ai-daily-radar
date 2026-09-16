/**
 * 日报流水线的外部看门狗 + 准点投递触发器。
 *
 * 一天四道 cron(北京时间):
 *   07:50  起跑生成——只写文件、提交存档,一条消息都不发
 *   08:30  准点投递——把已生成好的日报推进钉钉群 + 发邮件  ← 这一道决定日报几点到
 *   08:40  哨兵一——没送达就补救(缺什么补什么)
 *   09:10  哨兵二——最后一次补救,给「08:40 才补跑生成」留出完成时间
 *
 * 为什么生成和投递要拆成两条流水线:送达要准点,而准点只能靠「按点触发投递」。
 * 合在一起时送达时刻 = 起跑时刻 + 生成耗时,生成快慢直接把送达时间带跑
 * (2026-09-01~06 实测生成 8~13 分钟,日报 08:02~08:03 就发出去了,比约定的 08:30
 * 早半小时);而想钉死 08:30 就只能在 runner 上 sleep 等点,那正是 2026-08-30
 * 烧穿 Actions 月度额度的原因。拆开之后生成想跑多久跑多久,投递永远 08:30。
 *
 * 为什么触发放在 GitHub 外面:GitHub Actions 的 schedule 触发时刻完全不受控。
 * 本仓库实测 2026-08-17~26 延迟稳定在 10 分钟上下,但 08-27 三道 cron 全部漂到
 * 4~5 小时之后(`50 21` 那道 02:12 UTC 才触发),08-28 一道都没触发,两天的日报
 * 都是人工补跑的。把起跑时间再往前提救不了 08-28 那种情况——那不是触发晚了,
 * 是压根没触发。workflow_dispatch 是即时的,从没漂过。
 *
 * 告警走钉钉而不是「再 dispatch 一个告警 workflow」:被监控的东西不能是告警的前提,
 * 否则 Actions 真出问题时告警会跟着一起哑掉。
 */

// 必须和 wrangler.toml 的 [triggers] crons 逐字一致
const CRON_GENERATE = "50 23 * * *"; // 北京 07:50
const CRON_DELIVER = "30 0 * * *"; // 北京 08:30
const CRON_SENTINEL_1 = "40 0 * * *"; // 北京 08:40
const CRON_SENTINEL_2 = "10 1 * * *"; // 北京 09:10

const GH = "https://api.github.com";
const UA = "ai-daily-radar-watchdog";

/** 北京时间的今天(YYYY-MM-DD)。Worker 跑在 UTC,不能直接 toISOString。 */
function todayInBeijing() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": UA,
  };
}

async function detail(res) {
  return (await res.text().catch(() => "")).slice(0, 300);
}

/**
 * 远端 main 上某个文件的字节数。确实不存在返回 0;查不到则抛异常。
 *
 * 「不存在」和「查不到」必须分开。任何一种失败都当成「还没有」的话,网络抖一下
 * 就会 dispatch 投递,结果是往公司群重复推一遍日报。宁可这次不动作:
 * 后面还有哨兵会再查一次,GitHub 那两道兜底 cron 也还在。
 */
async function fileSize(env, path) {
  const res = await fetch(`${GH}/repos/${env.REPO}/contents/${path}`, {
    headers: ghHeaders(env),
  });
  if (res.status === 404) return 0;
  if (!res.ok) throw new Error(`查询 ${path} 失败 HTTP ${res.status}:${await detail(res)}`);
  const body = await res.json();
  return typeof body.size === "number" ? body.size : 0;
}

/** 今天的日报生成好了没(生成流水线提交存档 = 就绪信号)。 */
const reportSize = (env, day) => fileSize(env, `reports/${day}.md`);

/**
 * 今天的日报投递出去了没。
 *
 * 【注意】拆成两条流水线之后,「reports/<day>.md 存在」只证明生成完了,不代表进群了。
 * 判断是否送达必须看这份投递回执——它由投递流水线在钉钉推送成功之后立刻提交。
 * 早先两者是同一件事,那时哨兵查的就是日报文件本身。
 */
const receiptSize = (env, day) => fileSize(env, `state/delivered/${day}.txt`);

/**
 * 某条流水线正在跑或排队的 run 数量。这是防重复推送的第二道闸:
 * GitHub 那两道兜底 cron 万一因别的原因已经在跑,或者你自己刚手动 Run 过一次,
 * 这时候再 dispatch 就是两道 run 各推一次。
 */
async function activeRuns(env, workflow) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${workflow}/runs?per_page=20`,
    { headers: ghHeaders(env) },
  );
  if (!res.ok) throw new Error(`查询 ${workflow} 的 run 列表失败 HTTP ${res.status}:${await detail(res)}`);
  const body = await res.json();
  const ACTIVE = new Set(["queued", "in_progress", "waiting", "pending", "requested"]);
  return (body.workflow_runs || []).filter((r) => ACTIVE.has(r.status)).length;
}

async function dispatch(env, workflow) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(env), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  if (res.status !== 204) throw new Error(`dispatch ${workflow} 失败 HTTP ${res.status}:${await detail(res)}`);
}

/** 钉钉加签推送。签名算法和 scripts/send_dingtalk.py 一致。 */
async function dingtalk(env, title, text) {
  if (!env.DINGTALK_WEBHOOK || !env.DINGTALK_SECRET) {
    console.log("未配置钉钉凭据,跳过告警");
    return;
  }
  const ts = Date.now().toString();
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(env.DINGTALK_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, enc.encode(`${ts}\n${env.DINGTALK_SECRET}`));
  const sign = encodeURIComponent(btoa(String.fromCharCode(...new Uint8Array(mac))));
  const sep = env.DINGTALK_WEBHOOK.includes("?") ? "&" : "?";
  const res = await fetch(`${env.DINGTALK_WEBHOOK}${sep}timestamp=${ts}&sign=${sign}`, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify({ msgtype: "markdown", markdown: { title, text } }),
  });
  // 钉钉失败时 HTTP 状态码仍是 200,真正的成败看响应体的 errcode
  const body = await res.json().catch(() => ({}));
  if (body.errcode !== 0) throw new Error(`钉钉推送失败:${JSON.stringify(body)}`);
}

/** 北京 07:50:起跑今天的生成。 */
async function runGenerate(env) {
  const day = todayInBeijing();
  const size = await reportSize(env, day);
  if (size > 0) return `远端已有 reports/${day}.md(${size} 字节),无需起跑`;

  const running = await activeRuns(env, env.WORKFLOW_GENERATE);
  if (running > 0) return `已有 ${running} 道生成 run 在跑/排队(多半是 GitHub 的兜底 cron 已触发),不重复起跑`;

  await dispatch(env, env.WORKFLOW_GENERATE);
  return `远端无 ${day} 的日报且无 run 在跑,已 dispatch 生成,预计 08:03 前后写完`;
}

/**
 * 北京 08:30:准点投递。这一道就是「日报几点进群」。
 *
 * 生成还没跑完的话不硬投——投递流水线拿不到文件只会红一次。这里直接告警说明原因,
 * 补救交给 08:40 / 09:10 两道哨兵。
 */
async function runDeliver(env) {
  const day = todayInBeijing();

  if ((await receiptSize(env, day)) > 0) return `${day} 已有投递回执,今天已经投过,不重复投递`;

  const delivering = await activeRuns(env, env.WORKFLOW_DELIVER);
  if (delivering > 0) return `已有 ${delivering} 道投递 run 在跑/排队,不重复投递`;

  const size = await reportSize(env, day);
  if (size === 0) {
    const generating = await activeRuns(env, env.WORKFLOW_GENERATE);
    await dingtalk(
      env,
      `⚠️ AI 日报 08:30 无法投递 ${day}`,
      [
        "## ⚠️ 到点了但日报还没生成好",
        "",
        `- 日期:${day}`,
        `- 现象:08:30 该投递了,远端却还没有 reports/${day}.md`,
        `- 生成流水线:${generating > 0 ? `还有 ${generating} 道 run 在跑,可能只是慢了` : "没有任何 run 在跑,07:50 那道起跑没成事"}`,
        "- 处理:08:40 和 09:10 两道哨兵会继续补救,生成一好就自动补投",
        `- [查看运行](https://github.com/${env.REPO}/actions)`,
      ].join("\n"),
    );
    return `${day} 尚未生成完,无法投递,已告警,等哨兵补救`;
  }

  await dispatch(env, env.WORKFLOW_DELIVER);
  return `已 dispatch 投递 ${day} 的日报(${size} 字节)`;
}

/**
 * 北京 08:40 / 09:10:查岗。缺什么补什么。
 *
 * last=true 是当天最后一次机会,补不动就把话说死,别让人以为还有后手。
 */
async function runSentinel(env, { last }) {
  const day = todayInBeijing();

  if ((await receiptSize(env, day)) > 0) return `${day} 已有投递回执,日报已送达`;

  // 投递 run 还在跑就等它,别再 dispatch 一道,那是往公司群重复推送。
  const delivering = await activeRuns(env, env.WORKFLOW_DELIVER);
  if (delivering > 0) return `${day} 尚无回执,但有 ${delivering} 道投递 run 正在跑,等它自己完成`;

  const size = await reportSize(env, day);

  // 日报已就绪却没投出去:08:30 那道投递没成事(Worker 挂了 / dispatch 失败 / run 红了)。
  if (size > 0) {
    await dingtalk(
      env,
      `⚠️ AI 日报未按时投递 ${day}`,
      [
        "## ⚠️ 日报已生成,但没能按时进群",
        "",
        `- 日期:${day}`,
        `- 现象:日报早已就绪(${size} 字节),却查不到投递回执`,
        "- 判断:08:30 那道投递没成事(dispatch 没打进去,或投递 run 失败了)",
        "- 处理:哨兵已自动补投,稍后应能收到",
        `- [查看运行](https://github.com/${env.REPO}/actions)`,
      ].join("\n"),
    );
    await dispatch(env, env.WORKFLOW_DELIVER);
    return `${day} 日报已就绪但无回执,已告警并 dispatch 补投`;
  }

  // 连日报都还没有。
  const generating = await activeRuns(env, env.WORKFLOW_GENERATE);
  if (generating > 0) {
    return last
      ? `${day} 仍在生成中(${generating} 道 run),已是最后一道哨兵,生成完需要手动投递`
      : `${day} 尚未生成完,但有 ${generating} 道生成 run 正在跑,等下一道哨兵再看`;
  }

  await dingtalk(
    env,
    `⚠️ AI 日报未送达 ${day}`,
    [
      "## ⚠️ AI 日报未送达",
      "",
      `- 日期:${day}`,
      `- 现象:仍无 reports/${day}.md,且 GitHub 上没有任何 run 在跑`,
      "- 判断:07:50 那道起跑没成事(或 run 已失败退出),看门狗已自动 dispatch 补跑生成",
      last
        ? "- ⚠️ 这已是当天最后一道哨兵:生成完之后【不会】再自动投递,需要手动 Run 一次投递流水线"
        : "- 生成好之后,09:10 那道哨兵会自动补投",
      "- 若补跑也起不来、报 `job was not started`,那是 GitHub Actions 月度分钟额度耗尽",
      `- [查看运行](https://github.com/${env.REPO}/actions)`,
    ].join("\n"),
  );
  await dispatch(env, env.WORKFLOW_GENERATE);
  return `${day} 仍未生成且无 run 在跑,已告警并 dispatch 补跑生成`;
}

function modeForCron(cron) {
  if (cron === CRON_GENERATE) return "generate";
  if (cron === CRON_DELIVER) return "deliver";
  if (cron === CRON_SENTINEL_1) return "sentinel";
  if (cron === CRON_SENTINEL_2) return "sentinel-last";
  // wrangler.toml 改了 cron 但这里的常量没跟着改。按哨兵处理:它会告警,
  // 能让这个配置错误浮出水面,而不是无声地变成一次多余的起跑或重复投递。
  console.error(`未知 cron「${cron}」,与 index.js 的常量对不上,按哨兵处理`);
  return "sentinel-last";
}

async function run(mode, env) {
  try {
    let msg;
    if (mode === "generate") msg = await runGenerate(env);
    else if (mode === "deliver") msg = await runDeliver(env);
    else msg = await runSentinel(env, { last: mode === "sentinel-last" });
    console.log(`[${mode}] ${msg}`);
    return msg;
  } catch (err) {
    const msg = `[${mode}] 失败:${err.message}`;
    console.error(msg);
    // generate 出错不告警——后面三道 cron 都会再查一次,不值得为一次网络抖动吵醒人。
    // deliver 和哨兵出错必须喊出来:那时候已经贴着送达时间了,没有多少补救余地。
    if (mode !== "generate") {
      await dingtalk(
        env,
        "⚠️ AI 日报看门狗异常",
        `## ⚠️ 看门狗没能确认日报状态\n\n- 环节:${mode}\n- 错误:${err.message}\n- 请手动确认 [Actions](https://github.com/${env.REPO}/actions)`,
      ).catch((e) => console.error(`[${mode}] 连告警也失败了:${e.message}`));
    }
    return msg;
  }
}

/**
 * 探测 token 有没有 Actions: Write——故意用一个不存在的 ref 去 dispatch:
 *   403 = 没有写权限
 *   422 = 有写权限,只是 ref 不存在(这正是我们要的)
 * 这样能验权限而不会真的建出一道 run。真 dispatch 一次投递的代价是往公司群重推一遍日报,
 * 所以配 token / 轮换 token 之后用这个探针确认,别用真触发去试。
 */
async function probeDispatchPermission(env, workflow) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${workflow}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(env), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "watchdog-permission-probe-does-not-exist" }),
    },
  );
  const body = await detail(res);
  if (res.status === 422) return { workflow, ok: true, status: res.status, note: "有 Actions: Write 权限" };
  if (res.status === 403) return { workflow, ok: false, status: res.status, note: "缺 Actions: Write 权限", body };
  if (res.status === 404) return { workflow, ok: false, status: res.status, note: "仓库/工作流不可见,检查 token 的仓库范围", body };
  return { workflow, ok: false, status: res.status, note: "预期之外的响应", body };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(modeForCron(event.cron), env));
  },

  // 部署后的验证/演练入口。密钥不对一律 404,不确认这个路径是否存在。
  //
  // 这里也是外部兜底通道的入口(见 docs/external-cron-backstop.md):
  // Cloudflare 的 cron 调度器整个哑掉时(2026-09-09 就这么栽过一次,触发器还在、
  // 脚本还在、调用数为 0),外部定时服务按点打这几个 /run/* 就能顶上。
  // 四个 run 分支自己都做了幂等判断(查日报、查回执、查在跑的 run),
  // 和 Cloudflare 的 cron 撞车也不会重复往公司群推。
  async fetch(request, env) {
    const url = new URL(request.url);
    // 优先读请求头:密钥填进第三方定时服务的 URL 输入框的话,会一路留在它的配置里
    // 和 Cloudflare 的请求日志里。query 参数继续支持,手工 curl 时方便。
    const presented = request.headers.get("X-Control-Key") ?? url.searchParams.get("key");
    if (!env.CONTROL_KEY || presented !== env.CONTROL_KEY) {
      return new Response("not found\n", { status: 404 });
    }
    if (url.pathname === "/status") {
      const day = todayInBeijing();
      try {
        return Response.json({
          day,
          reportSize: await reportSize(env, day),
          receiptSize: await receiptSize(env, day),
          activeGenerateRuns: await activeRuns(env, env.WORKFLOW_GENERATE),
          activeDeliverRuns: await activeRuns(env, env.WORKFLOW_DELIVER),
        });
      } catch (err) {
        return Response.json({ day, error: err.message }, { status: 502 });
      }
    }
    if (url.pathname === "/probe") {
      try {
        return Response.json([
          await probeDispatchPermission(env, env.WORKFLOW_GENERATE),
          await probeDispatchPermission(env, env.WORKFLOW_DELIVER),
        ]);
      } catch (err) {
        return Response.json({ ok: false, error: err.message }, { status: 502 });
      }
    }
    if (url.pathname === "/run/generate") return new Response((await run("generate", env)) + "\n");
    if (url.pathname === "/run/deliver") return new Response((await run("deliver", env)) + "\n");
    if (url.pathname === "/run/sentinel") return new Response((await run("sentinel", env)) + "\n");
    if (url.pathname === "/run/sentinel-last") return new Response((await run("sentinel-last", env)) + "\n");
    return new Response("not found\n", { status: 404 });
  },
};
