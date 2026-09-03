#!/usr/bin/env node
/**
 * Owns the Lightroom plugin sockets (1:1) and multiplexes clients over TCP.
 * Default listen: 127.0.0.1:58770  JSON-lines {id, action, params}
 */
import net from "node:net";
import { existsSync, writeFileSync, unlinkSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

function automaatDist() {
  const fromEnv = process.env.LRMCP_AUTOMAAT_DIST;
  const fallback = join(homedir(), "repositories/lightroom-mcp-automaat/server/dist");
  const dist = fromEnv || fallback;
  if (!existsSync(join(dist, "plugin-socket.js"))) {
    throw new Error(`automaat dist not found at ${dist}. Set LRMCP_AUTOMAAT_DIST.`);
  }
  return dist;
}

const dist = automaatDist();
const { PluginSocket } = await import(pathToFileURL(join(dist, "plugin-socket.js")).href);
const { Dispatcher } = await import(pathToFileURL(join(dist, "dispatcher.js")).href);
const { readToken } = await import(pathToFileURL(join(dist, "token.js")).href);

const REQUEST_PORT = Number(process.env.LIGHTROOM_MCP_REQUEST_PORT || 58763);
const RESPONSE_PORT = Number(process.env.LIGHTROOM_MCP_RESPONSE_PORT || 58764);
const GATEWAY_HOST = process.env.LR_AGENT_GATEWAY_HOST || "127.0.0.1";
const GATEWAY_PORT = Number(process.env.LR_AGENT_GATEWAY_PORT || 58770);
const PID_FILE = join(homedir(), ".config", "lightroom-mcp", "gateway.pid");

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function waitConnected(sock, label, timeoutMs = 8000) {
  return new Promise((resolve, reject) => {
    const t0 = Date.now();
    const tick = () => {
      if (sock.isConnected()) return resolve();
      if (Date.now() - t0 > timeoutMs) {
        return reject(new Error(`${label} not connected. Is Lightroom MCP Start Server running?`));
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
  actionTimeoutsMs: {
    export_photos: 180_000,
    import_photos: 180_000,
    ping: 10_000,
    create_ai_mask: 90_000,
    set_auto_tone: 30_000,
  },
  log: (m) => console.error(m),
});

requestSocket = new PluginSocket({
  port: REQUEST_PORT,
  label: "request",
  log: (m) => console.error(m),
});
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

const server = net.createServer((sock) => {
  sock.setEncoding("utf8");
  let buf = "";
  sock.on("data", async (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let req;
      try {
        req = JSON.parse(line);
      } catch {
        sock.write(JSON.stringify({ error: "invalid json" }) + "\n");
        continue;
      }
      const action = req.action;
      const params = req.params || {};
      const id = req.id;
      try {
        const resp = await dispatcher.call(action, params);
        if (resp.error) {
          sock.write(JSON.stringify({ id, error: resp.error }) + "\n");
        } else {
          sock.write(JSON.stringify({ id, result: resp.result }) + "\n");
        }
      } catch (err) {
        sock.write(JSON.stringify({ id, error: String(err.message || err) }) + "\n");
      }
    }
  });
});

server.listen(GATEWAY_PORT, GATEWAY_HOST, () => {
  try {
    writeFileSync(PID_FILE, String(process.pid));
  } catch {
    /* ignore */
  }
  console.error(`lr-gateway listening ${GATEWAY_HOST}:${GATEWAY_PORT} pid=${process.pid}`);
});

function shutdown() {
  try {
    unlinkSync(PID_FILE);
  } catch {
    /* ignore */
  }
  requestSocket.stop();
  responseSocket.stop();
  server.close();
  process.exit(0);
}
process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
