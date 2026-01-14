# OpenHands on Unraid

## Quick Start

1. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

2. **Set Required Values**
   ```bash
   # Generate secret key
   openssl rand -hex 32
   
   # Edit .env:
   OPENHANDS_SECRET_KEY=<generated-key>
   OLLAMA_HOST_IP=<windows-pc-ip>
   OLLAMA_MODEL=<chosen-model>
   ```

3. **Deploy**
   ```bash
   docker-compose up -d
   ```

4. **Verify**
   ```bash
   # Check health
   curl http://<unraid-ip>:3000/health
   
   # Check logs
   docker-compose logs -f openhands
   ```

## Configuration

All configuration is in `config/config.toml`:
- LLM provider settings
- Network configuration
- Agent limits
- Security settings

## Troubleshooting

See `../../docs/openhands-ollama-architecture.md` for detailed troubleshooting guide.
