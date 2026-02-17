#!/usr/bin/env node

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { tools, handlers } from './tools.js';
import express from 'express';

const server = new Server(
  {
    name: 'obsidian-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  const handler = handlers[name];
  if (!handler) {
    throw new Error(`Unknown tool: ${name}`);
  }

  try {
    const result = await handler(args);
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(result, null, 2)
        }
      ]
    };
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: `Error: ${error.message}`
        }
      ],
      isError: true
    };
  }
});

async function main() {
  const mode = process.env.TRANSPORT_MODE || 'stdio';
  const port = process.env.PORT || 6977;

  if (mode === 'http') {
    const app = express();
    app.use(express.json());

    app.get('/health', (req, res) => {
      res.json({ status: 'healthy', mode: 'http', server: 'obsidian-mcp-server' });
    });

    // Create transport once at startup (stateless mode for Director compatibility)
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined, // Stateless mode
    });

    // Connect server to transport
    await server.connect(transport);
    await transport.start(); // Start the transport

    // Handle all MCP requests through the transport
    app.post('/mcp', async (req, res) => {
      try {
        await transport.handleRequest(req, res, req.body);
      } catch (error) {
        console.error('HTTP request error:', error);
        if (!res.headersSent) {
          res.status(500).json({ error: error.message });
        }
      }
    });

    // Handle GET requests for SSE (if client uses standalone SSE)
    app.get('/mcp', async (req, res) => {
      try {
        await transport.handleRequest(req, res);
      } catch (error) {
        console.error('SSE request error:', error);
        if (!res.headersSent) {
          res.status(500).json({ error: error.message });
        }
      }
    });

    app.listen(port, () => {
      console.error(`Obsidian MCP Server running on HTTP mode (Streamable) at port ${port}`);
    });
  } else {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    console.error('Obsidian MCP Server running on stdio');
  }
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
