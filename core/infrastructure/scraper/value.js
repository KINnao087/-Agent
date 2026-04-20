const crypto = require("crypto");

const CODES = [
  "W", "l", "k", "B", "Q",
  "g", "f", "i", "i", "r",
  "v", "6", "A", "K", "N",
  "k", "4", "L", "1", "8",
];

function normalizePath(path = "/") {
  // 在生成签名前，先按站点规则规范化请求路径。
  return String(path ?? "/").toLowerCase();
}

function normalizePayload(payload = {}) {
  // 将请求体转换成签名使用的小写 JSON 字符串。
  if (payload === undefined || payload === null || payload === "") {
    return "{}";
  }

  if (typeof payload === "string") {
    return payload.toLowerCase();
  }

  return JSON.stringify(payload).toLowerCase();
}

function readGlobalTid() {
  // 优先从浏览器全局变量或进程环境变量中读取 tid。
  if (typeof globalThis !== "undefined") {
    if (typeof globalThis.tid === "string" && globalThis.tid) {
      return globalThis.tid;
    }

    if (
      globalThis.window
      && typeof globalThis.window.tid === "string"
      && globalThis.window.tid
    ) {
      return globalThis.window.tid;
    }
  }

  if (typeof process !== "undefined" && process.env.QCC_TID) {
    return process.env.QCC_TID;
  }

  return "";
}

function resolveTid(explicitTid) {
  // 优先使用显式传入的 tid，否则回退到全局变量或环境变量。
  const tid = explicitTid ?? readGlobalTid();

  if (!tid) {
    throw new Error(
      "Missing tid. Pass totfunc(path, data, tid), or set globalThis.tid / process.env.QCC_TID.",
    );
  }

  return String(tid).toLowerCase();
}

function layer3(path = "/") {
  // 根据规范化后的路径生成 HMAC key。
  const normalized = normalizePath(path);
  const doubled = normalized + normalized;
  let out = "";

  for (let i = 0; i < doubled.length; i += 1) {
    const idx = doubled[i].charCodeAt(0) % CODES.length;
    out += CODES[idx];
  }

  return out;
}

function layer4(message, key) {
  // 计算原始的 SHA-512 HMAC 摘要。
  return crypto
    .createHmac("sha512", key)
    .update(message, "utf8")
    .digest("hex");
}

function totfunc(path = "/", data = {}, explicitTid) {
  // 生成搜索接口需要的动态请求头 value。
  const normalizedPath = normalizePath(path);
  const normalizedPayload = normalizePayload(data);
  const tid = resolveTid(explicitTid);

  // 站点会在路径和请求体之间拼接固定字面量 pathString。
  const message = normalizedPath + "pathString" + normalizedPayload + tid;
  return layer4(message, layer3(normalizedPath));
}

module.exports = {
  CODES,
  layer3,
  layer4,
  normalizePath,
  normalizePayload,
  resolveTid,
  totfunc,
};

if (require.main === module) {
  const [
    ,
    ,
    pathArg = "/api/usersearch/getfilterlist?type=2",
    payloadArg = "{}",
    tidArg,
  ] = process.argv;

  try {
    console.log(totfunc(pathArg, payloadArg, tidArg));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
