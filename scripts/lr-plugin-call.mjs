#!/usr/bin/env node
/**
 * Direct Lightroom plugin client (no MCP stdio, no python SDK, no WorkBuddy).
 *
 * Talks NDJSON + token to the automaat Lua plugin on :58763/:58764 using
 * automaat's own PluginSocket + Dispatcher. This is the path that actually
 * can call set_develop_settings (WorkBuddy's oneOf validator cannot).
 *
 * Prerequisite: Lightroom Classic plugin "Start Server" is running, and
 * nothing else holds the plugin sockets (WorkBuddy's lightroom MCP occupies
 * them 1:1). If WorkBuddy is connected, stop that connector first.
 *
 * Usage:
 *   node scripts/lr-plugin-call.mjs ping
 *   node scripts/lr-plugin-call.mjs get_photo_metadata '{"photo_id":"346763"}'
 *   node scripts/lr-plugin-call.mjs set_develop_settings '{"photo_id":"346763","settings":{"Exposure2012":0.15,"Blacks2012":5,"Temperature":5850,"SaturationAdjustmentBlue":-15}}'
 *   node scripts/lr-plugin-call.mjs export_photos '{"photo_ids":["346763"],"destination":"/tmp/lr-retouch","format":"jpeg","quality":90,"width":1080,"height":1080}'
 */
import { existsSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

function automaatDist() {
  const fromEnv = process.env.LRMCP_AUTOMAAT_DIST;
  const fallback = join(homedir(), "repositories/lightroom-mcp-automaat/server/dist");
  const dist = fromEnv || fallback;
  if (!existsSync(join(dist, "plugin-socket.js"))) {
    throw new Error(
      `automaat dist not found at ${dist} (need plugin-socket.js). Set LRMCP_AUTOMAAT_DIST.`,
    );
  }
  return dist;
}

const dist = automaatDist();
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
            `${label} socket not connected after ${timeoutMs}ms. ` +
              `Is the Lightroom plugin listening, and is WorkBuddy's lightroom MCP disconnected?`,
          ),
        );
      }
      setTimeout(tick, 50);
    };
    tick();
  });
}

async function withPlugin(fn) {
  let requestSocket;
  const dispatcher = new Dispatcher({
    send: (line) => requestSocket.send(line),
    getToken: () => readToken(),
    timeoutMs: 30_000,
    actionTimeoutsMs: { export_photos: 180_000, import_photos: 180_000, ping: 10_000 },
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

  try {
    return await fn(dispatcher);
  } finally {
    requestSocket.stop();
    responseSocket.stop();
  }
}

async function main() {
  const action = process.argv[2];
  if (!action || action === "-h" || action === "--help") {
    console.error(`usage: lr-plugin-call.mjs <action> [json-params]
token file: ${join(homedir(), ".config", "lightroom-mcp", "token")}
ports: ${REQUEST_PORT}/${RESPONSE_PORT}`);
    process.exit(action ? 0 : 2);
  }
  let params = {};
  if (process.argv[3]) {
    params = JSON.parse(process.argv[3]);
  }

  const result = await withPlugin(async (dispatcher) => {
    const resp = await dispatcher.call(action, params);
    if (resp.error) {
      throw new Error(`${action}: ${resp.error}`);
    }
    return resp.result;
  });
  process.stdout.write(JSON.stringify(result, null, 2) + "\n");
}

main().catch((err) => {
  console.error("FATAL", err.message || err);
  process.exit(1);
});
