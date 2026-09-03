#!/usr/bin/env node
/**
 * Lightroom plugin client. Prefers the local gateway (many clients, one plugin
 * socket). Falls back to a direct LrSocket connection if the gateway is down.
 *
 * Usage:
 *   node scripts/lr-plugin-call.mjs ping
 *   node scripts/lr-plugin-call.mjs get_photo_metadata '{"photo_id":"346763"}'
 */
import net from "node:net";
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

const GATEWAY = process.env.LR_AGENT_GATEWAY || "127.0.0.1:58770";
const DIRECT = process.env.LR_AGENT_DIRECT === "1";

function reloadHint(msg) {
  const s = String(msg || "");
  if (/Unknown action/i.test(s)) {
    return `${s} Reload Lightroom MCP in Plug-in Manager (File → Plug-in Manager).`;
  }
  return s;
}

function callGateway(action, params) {
  const [host, portStr] = GATEWAY.split(":");
  const port = Number(portStr || 58770);
  return new Promise((resolve, reject) => {
    const sock = net.connect({ host, port }, () => {
      sock.write(JSON.stringify({ action, params }) + "\n");
    });
    sock.setEncoding("utf8");
    let buf = "";
    const t = setTimeout(() => {
      sock.destroy();
      reject(new Error("gateway timeout"));
    }, 120_000);
    sock.on("data", (chunk) => {
      buf += chunk;
      if (buf.includes("\n")) {
        clearTimeout(t);
        sock.end();
        try {
          const msg = JSON.parse(buf.trim().split("\n")[0]);
          if (msg.error) reject(new Error(reloadHint(msg.error)));
          else resolve(msg.result);
        } catch (e) {
          reject(e);
        }
      }
    });
    sock.on("error", (err) => {
      clearTimeout(t);
      reject(err);
    });
  });
}

async function callDirect(action, params) {
  const fromEnv = process.env.LRMCP_AUTOMAAT_DIST;
  const fallback = join(homedir(), "repositories/lightroom-mcp-automaat/server/dist");
  const dist = fromEnv || fallback;
  if (!existsSync(join(dist, "plugin-socket.js"))) {
    throw new Error(`automaat dist not found at ${dist}. Set LRMCP_AUTOMAAT_DIST.`);
  }
  const { PluginSocket } = await import(pathToFileURL(join(dist, "plugin-socket.js")).href);
  const { Dispatcher } = await import(pathToFileURL(join(dist, "dispatcher.js")).href);
  const { readToken } = await import(pathToFileURL(join(dist, "token.js")).href);
  const REQUEST_PORT = Number(process.env.LIGHTROOM_MCP_REQUEST_PORT || 58763);
  const RESPONSE_PORT = Number(process.env.LIGHTROOM_MCP_RESPONSE_PORT || 58764);

  function sleep(ms) {
    return new Promise((r) => setTimeout(r, ms));
  }
  function waitConnected(sock, label, timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
      const t0 = Date.now();
      const tick = () => {
        if (sock.isConnected()) return resolve();
        if (Date.now() - t0 > timeoutMs) {
          return reject(
            new Error(
              `${label} socket not connected. Start lr-gateway.mjs or disconnect other MCP clients.`,
            ),
          );
        }
        setTimeout(tick, 50);
      };
      tick();
    });
  }

  let requestSocket;
  const dispatcher = new Dispatcher({
    send: (line) => requestSocket.send(line),
    getToken: () => readToken(),
    timeoutMs: 30_000,
    actionTimeoutsMs: { export_photos: 180_000, create_ai_mask: 90_000, ping: 10_000 },
    log: (m) => console.error(m),
  });
  requestSocket = new PluginSocket({ port: REQUEST_PORT, label: "request", log: (m) => console.error(m) });
  requestSocket.connect();
  await waitConnected(requestSocket, "request");
  await sleep(250);
  const responseSocket = new PluginSocket({
    port: RESPONSE_PORT,
    label: "response",
    onLine: (line) => dispatcher.handleResponseLine(line),
    log: (m) => console.error(m),
  });
  responseSocket.connect();
  await waitConnected(responseSocket, "response");
  await sleep(150);
  try {
    const resp = await dispatcher.call(action, params);
    if (resp.error) throw new Error(reloadHint(resp.error));
    return resp.result;
  } finally {
    requestSocket.stop();
    responseSocket.stop();
  }
}

async function main() {
  const action = process.argv[2];
  if (!action || action === "-h" || action === "--help") {
    console.error(`usage: lr-plugin-call.mjs <action> [json-params]
gateway: ${GATEWAY}  (set LR_AGENT_DIRECT=1 to skip)`);
    process.exit(action ? 0 : 2);
  }
  let params = {};
  if (process.argv[3]) params = JSON.parse(process.argv[3]);

  let result;
  if (!DIRECT) {
    try {
      result = await callGateway(action, params);
    } catch (err) {
      if (err.code === "ECONNREFUSED" || /gateway timeout/.test(err.message)) {
        console.error(`[lr-plugin-call] gateway ${GATEWAY} down, trying plugin sockets`);
        result = await callDirect(action, params);
      } else {
        throw err;
      }
    }
  } else {
    result = await callDirect(action, params);
  }
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
}

main().catch((err) => {
  console.error("FATAL", reloadHint(err.message || err));
  process.exit(1);
});
