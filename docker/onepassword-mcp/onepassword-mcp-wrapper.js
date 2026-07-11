#!/usr/bin/env node

import { spawn } from 'node:child_process';

const child = spawn('1password-mcp', process.argv.slice(2), {
  stdio: ['pipe', 'pipe', 'inherit'],
  env: process.env,
});

const upstreamResourceScheme = '1password://';
const proxyResourceScheme = 'onepassword://';
const configResourceUri = `${proxyResourceScheme}config`;

function writeJson(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function interceptMcpRequest(line) {
  try {
    const message = JSON.parse(line);
    if (message.method === 'resources/read' && message.params?.uri === configResourceUri) {
      writeJson({
        jsonrpc: '2.0',
        id: message.id,
        result: {
          contents: [
            {
              uri: configResourceUri,
              mimeType: 'application/json',
              text: JSON.stringify({
                name: '1password-mcp',
                package: '@takescake/1password-mcp',
                version: process.env.ONEPASSWORD_MCP_VERSION ?? 'unknown',
                tokenSource: process.env.OP_SERVICE_ACCOUNT_TOKEN ? 'env' : 'missing',
              }),
            },
          ],
        },
      });
      return true;
    }
  } catch {
    return false;
  }
  return false;
}

function normalizeMcpRequest(line) {
  try {
    const message = JSON.parse(line);
    const uri = message.params?.uri;
    if (message.method === 'resources/read' && uri?.startsWith(proxyResourceScheme)) {
      message.params.uri = uri.replace(proxyResourceScheme, upstreamResourceScheme);
    }
    return JSON.stringify(message);
  } catch {
    return line;
  }
}

function normalizeMcpResponse(line) {
  try {
    const message = JSON.parse(line);
    if (Array.isArray(message.result?.tools)) {
      message.result.tools = message.result.tools.map((tool) => {
        const { execution, ...standardTool } = tool;
        return standardTool;
      });
    }
    if (Array.isArray(message.result?.resources)) {
      message.result.resources = message.result.resources
        .filter((resource) => resource.uri === `${upstreamResourceScheme}config`)
        .map((resource) => ({
          ...resource,
          uri: resource.uri?.replace(upstreamResourceScheme, proxyResourceScheme),
        }));
    }
    return JSON.stringify(message);
  } catch {
    return line;
  }
}

function relayByLine(stream, onLine) {
  let buffer = '';
  stream.setEncoding('utf8');
  stream.on('data', (chunk) => {
    buffer += chunk;
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      onLine(line.replace(/\r$/, ''));
    }
  });
  stream.on('end', () => {
    if (buffer.length > 0) {
      onLine(buffer.replace(/\r$/, ''));
    }
  });
}

relayByLine(process.stdin, (line) => {
  if (!interceptMcpRequest(line)) {
    child.stdin.write(`${normalizeMcpRequest(line)}\n`);
  }
});
process.stdin.on('end', () => {
  child.stdin.end();
});
relayByLine(child.stdout, (line) => {
  process.stdout.write(`${normalizeMcpResponse(line)}\n`);
});

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal));
}

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
