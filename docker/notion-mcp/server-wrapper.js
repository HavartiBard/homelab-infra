const { spawn } = require('child_process');
const http = require('http');
const stream = require('stream');

// Create a duplex stream to handle MCP communication
class MCPStream extends stream.Duplex {
  constructor() {
    super();
    this.process = null;
  }

  start() {
    // Spawn the Notion MCP server process
    this.process = spawn('npx', ['-y', '@notionhq/notion-mcp-server'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    // Forward stdout to this stream's readable side
    this.process.stdout.on('data', (data) => {
      this.push(data);
    });

    // Handle errors
    this.process.stderr.on('data', (data) => {
      console.error('MCP Server Error:', data.toString());
    });

    this.process.on('error', (err) => {
      console.error('Process error:', err);
    });

    this.process.on('exit', (code) => {
      console.log(`MCP Server exited with code ${code}`);
    });
  }

  _write(chunk, encoding, callback) {
    if (this.process && this.process.stdin) {
      this.process.stdin.write(chunk, encoding, callback);
    } else {
      callback();
    }
  }

  _read() {
    // Reading is handled by stdout event handler
  }
}

// Create HTTP server to handle MCP requests
const server = http.createServer((req, res) => {
  if (req.method === 'POST' && req.url === '/mcp') {
    const mcpStream = new MCPStream();
    mcpStream.start();

    // Pipe request to MCP stream and response back
    req.pipe(mcpStream);
    mcpStream.pipe(res);

    // Handle connection close
    req.on('end', () => {
      mcpStream.end();
    });
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`Notion MCP HTTP wrapper listening on port ${PORT}`);
});
