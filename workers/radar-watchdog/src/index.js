/**
 * 日报流水线的外部看门狗。
 *
 * 北京 07:50 起跑今天的日报,北京 08:40 查岗——没送达就告警并补跑。
 *
 * 起跑时间就是送达时间减去生成耗时:workflow 生成完立刻投递,不再挂机等点。
 *
 * 为什么要有它:GitHub Actions 的 schedule 触发时刻完全不受控。本仓库实测
 * 2026-08-17~26 延迟稳定在 10 分钟上下,但 08-27 三道 cron 全部漂到 4~5 小时之后
 * (`50 21` 那道 02:12 UTC 才触发),08-28 一道都没触发,两天的日报都是人工补跑的。
 * 把起跑时间再往前提救不了 08-28 那种情况——那不是触发晚了,是压根没触发。
 * workflow_dispatch 是即时的,从没漂过,所以起跑的决定权移到 GitHub 外面。
 *
 * 告警走钉钉而不是「再 dispatch 一个告警 workflow」:被监控的东西不能是告警的前提,
 * 否则 Actions 真出问题时告警会跟着一起哑掉。
 */

// 必须和 wrangler.toml 的 [triggers] crons 逐字一致
const CRON_TRIGGER = "50 23 * * *"; // 北京 07:50
const CRON_SENTINEL = "40 0 * * *"; // 北京 08:40

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
 * 远端 main 上某天日报的字节数。确实不存在返回 0;查不到则抛异常。
 *
 * 「不存在」和「查不到」必须分开。任何一种失败都当成「今天还没出日报」的话,
 * 网络抖一下就会 dispatch,而 workflow_dispatch 会绕过工作流里那个
 * 「今天已生成就跳过」的守卫(守卫只拦 schedule),结果是往公司群重复推一遍日报。
 * 宁可这次不动作:GitHub 那道兜底 cron 还在,08:40 的哨兵也会再查一次。
 */
async function reportSize(env, day) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/contents/reports/${day}.md`,
    { headers: ghHeaders(env) },
  );
  if (res.status === 404) return 0;
  if (!res.ok) throw new Error(`查询日报失败 HTTP ${res.status}:${await detail(res)}`);
  const body = await res.json();
  return typeof body.size === "number" ? body.size : 0;
}

/**
 * 正在跑或排队的 run 数量。这是防重复推送的第二道闸:
 * GitHub 那道兜底 cron(01:00 UTC / 北京 09:00)万一提前不了、却因别的原因已经在跑,
 * 或者你自己刚手动 Run 过一次,这时候再 dispatch 就是两道 run 各推一次。
 */
async function activeRuns(env) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/runs?per_page=20`,
    { headers: ghHeaders(env) },
  );
  if (!res.ok) throw new Error(`查询 run 列表失败 HTTP ${res.status}:${await detail(res)}`);
  const body = await res.json();
  const ACTIVE = new Set(["queued", "in_progress", "waiting", "pending", "requested"]);
  return (body.workflow_runs || []).filter((r) => ACTIVE.has(r.status)).length;
}

async function dispatch(env) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(env), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "main" }),
    },
  );
  if (res.status !== 204) throw new Error(`dispatch 失败 HTTP ${res.status}:${await detail(res)}`);
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

async function runTrigger(env) {
  const day = todayInBeijing();
  const size = await reportSize(env, day);
  if (size > 0) return `远端已有 reports/${day}.md(${size} 字节),无需起跑`;

  const running = await activeRuns(env);
  if (running > 0) return `已有 ${running} 道 run 在跑/排队(多半是 GitHub 的 cron 已触发),不重复起跑`;

  await dispatch(env);
  return `远端无 ${day} 的日报且无 run 在跑,已 dispatch 起跑,预计 08:15 前后投递`;
}

async function runSentinel(env) {
  const day = todayInBeijing();
  const size = await reportSize(env, day);
  if (size > 0) return `reports/${day}.md 已在远端(${size} 字节),日报已送达`;

  const running = await activeRuns(env);
  // 生成完会立刻投递,还在跑就说明只是慢了,让它自己跑完,别再 dispatch 一道重复推送。
  if (running > 0) return `${day} 尚未送达,但有 ${running} 道 run 正在跑,等它自己投递`;

  await dingtalk(
    env,
    `⚠️ AI 日报未送达 ${day}`,
    [
      "## ⚠️ AI 日报未送达",
      "",
      `- 日期:${day}`,
      `- 现象:08:40 仍无 reports/${day}.md,且 GitHub 上没有任何 run 在跑`,
      "- 判断:07:50 那道起跑没成事(或 run 已失败退出),看门狗已自动 dispatch 补跑",
      "- 若补跑也起不来、报 `job was not started`,那是 GitHub Actions 月度分钟额度耗尽",
      `- [查看运行](https://github.com/${env.REPO}/actions)`,
    ].join("\n"),
  );
  await dispatch(env);
  return `${day} 08:40 仍未送达且无 run 在跑,已告警并 dispatch 补跑`;
}

function modeForCron(cron) {
  if (cron === CRON_TRIGGER) return "trigger";
  if (cron === CRON_SENTINEL) return "sentinel";
  // wrangler.toml 改了 cron 但这里的常量没跟着改。按 sentinel 处理:它会告警,
  // 能让这个配置错误浮出水面,而不是无声地变成一次多余的起跑。
  console.error(`未知 cron「${cron}」,与 index.js 的常量对不上,按 sentinel 处理`);
  return "sentinel";
}

async function run(mode, env) {
  try {
    const msg = await (mode === "trigger" ? runTrigger(env) : runSentinel(env));
    console.log(`[${mode}] ${msg}`);
    return msg;
  } catch (err) {
    const msg = `[${mode}] 失败:${err.message}`;
    console.error(msg);
    // trigger 出错不告警——08:40 的哨兵会再查一次,不值得为一次网络抖动吵醒人。
    // 哨兵自己出错才必须喊出来:它是最后一道防线,它哑了就没人知道日报没送到。
    if (mode === "sentinel") {
      await dingtalk(
        env,
        "⚠️ AI 日报哨兵异常",
        `## ⚠️ 哨兵没能确认日报是否送达\n\n- 错误:${err.message}\n- 请手动确认 [Actions](https://github.com/${env.REPO}/actions)`,
      ).catch((e) => console.error(`[${mode}] 连告警也失败了:${e.message}`));
    }
    return msg;
  }
}

/**
 * 探测 token 有没有 Actions: Write——故意用一个不存在的 ref 去 dispatch:
 *   403 = 没有写权限
 *   422 = 有写权限,只是 ref 不存在(这正是我们要的)
 * 这样能验权限而不会真的建出一道 run。真 dispatch 一次的代价是往公司群重推一遍日报,
 * 所以配 token / 轮换 token 之后用这个探针确认,别用真触发去试。
 */
async function probeDispatchPermission(env) {
  const res = await fetch(
    `${GH}/repos/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: { ...ghHeaders(env), "Content-Type": "application/json" },
      body: JSON.stringify({ ref: "watchdog-permission-probe-does-not-exist" }),
    },
  );
  const body = await detail(res);
  if (res.status === 422) return { ok: true, status: res.status, note: "有 Actions: Write 权限" };
  if (res.status === 403) return { ok: false, status: res.status, note: "缺 Actions: Write 权限", body };
  if (res.status === 404) return { ok: false, status: res.status, note: "仓库/工作流不可见,检查 token 的仓库范围", body };
  return { ok: false, status: res.status, note: "预期之外的响应", body };
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(run(modeForCron(event.cron), env));
  },

  // 部署后的验证/演练入口。密钥不对一律 404,不确认这个路径是否存在。
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!env.CONTROL_KEY || url.searchParams.get("key") !== env.CONTROL_KEY) {
      return new Response("not found\n", { status: 404 });
    }
    if (url.pathname === "/status") {
      const day = todayInBeijing();
      try {
        return Response.json({
          day,
          reportSize: await reportSize(env, day),
          activeRuns: await activeRuns(env),
        });
      } catch (err) {
        return Response.json({ day, error: err.message }, { status: 502 });
      }
    }
    if (url.pathname === "/probe") {
      try {
        return Response.json(await probeDispatchPermission(env));
      } catch (err) {
        return Response.json({ ok: false, error: err.message }, { status: 502 });
      }
    }
    if (url.pathname === "/run/trigger") return new Response((await run("trigger", env)) + "\n");
    if (url.pathname === "/run/sentinel") return new Response((await run("sentinel", env)) + "\n");
    return new Response("not found\n", { status: 404 });
  },
};
