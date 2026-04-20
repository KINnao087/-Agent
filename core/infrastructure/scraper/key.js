const crypto = require("crypto");

const CODES = [
  "W", "l", "k", "B", "Q",
  "g", "f", "i", "i", "r",
  "v", "6", "A", "K", "N",
  "k", "4", "L", "1", "8",
];

function normalizePath(path = "/") {
  // 按站点规则规范化请求路径，再参与签名。
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

function totfunc(path = "/", data = {}) {
  // 生成搜索接口需要的动态请求头 key。
  const normalizedPath = normalizePath(path);
  const normalizedPayload = normalizePayload(data);
  const digest = layer4(
    normalizedPath + normalizedPayload,
    layer3(normalizedPath),
  );

  return digest.toLowerCase().slice(8, 28);
}

module.exports = {
  CODES,
  layer3,
  layer4,
  normalizePath,
  normalizePayload,
  totfunc,
};

if (require.main === module) {
  const [, , pathArg = "/", payloadArg = "{}"] = process.argv;

  try {
    console.log(totfunc(pathArg, payloadArg));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
