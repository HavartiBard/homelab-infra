#!/usr/bin/env node

import { spawn } from 'node:child_process';

const child = spawn('1password-mcp', {
  stdio: ['pipe', 'pipe', 'inherit'],
  env: process.env,
});

function writeJson(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function emptyResultFor(request) {
  switch (request.method) {
    case 'resources/list':
      return { resources: [] };
    case 'resources/templates/list':
      return { resourceTemplates: [] };
    case 'prompts/list':
      return { prompts: [] };
    default:
      return null;
  }
}

function forwardOrIntercept(line) {
  if (!line.trim()) {
    return;
  }

  let request;
  try {
    request = JSON.parse(line);
  } catch {
    child.stdin.write(`${line}\n`);
    return;
  }

  const result = emptyResultFor(request);
  if (result) {
    writeJson({
      jsonrpc: '2.0',
      id: request.id ?? null,
      result,
    });
    return;
  }

  child.stdin.write(`${line}\n`);
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

relayByLine(process.stdin, forwardOrIntercept);
relayByLine(child.stdout, (line) => {
  process.stdout.write(`${line}\n`);
});

process.stdin.on('end', () => {
  child.stdin.end();
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 0);
});
