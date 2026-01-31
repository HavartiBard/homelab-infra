# Ollama on Windows Docker Desktop

## Quick Start

1. **Configure Environment**
   ```cmd
   copy .env.example .env
   # Edit .env if needed (defaults work for most)
   ```

2. **Deploy**
   ```cmd
   docker-compose up -d
   ```

3. **Pull Models**
   ```cmd
   docker exec ollama-windows ollama pull llama3.2:3b
   docker exec ollama-windows ollama pull qwen2.5-coder:7b
   ```

4. **Verify**
   ```cmd
   curl http://localhost:11434/api/tags
   ```

## Firewall Settings

Ensure Windows Firewall allows:
- Port 11434 inbound
- Docker Desktop traffic

## GPU Support

Requires:
- NVIDIA GPU with latest drivers
- WSL2 with GPU support
- NVIDIA Container Toolkit

## Models

Recommended models for OpenHands:
- `llama3.2:3b` - Fast, efficient
- `qwen2.5-coder:7b` - Code focused
- `deepseek-coder-v2:16b` - Advanced coding
