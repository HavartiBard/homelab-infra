# lm-eval-harness Runs

Use this container for standardized model/settings baselines.

Example OpenAI-compatible run against LiteLLM:

```bash
docker exec -it lm-eval-harness lm_eval \
  --model local-chat-completions \
  --model_args base_url=http://litellm:4000/v1/chat/completions,model=<model-name> \
  --tasks arc_easy,hellaswag \
  --num_fewshot 0 \
  --batch_size auto \
  --output_path /results/<run-name>.json
```

Record each run name with:

- model name and source
- runtime host
- quantization
- context length
- temperature/top_p/top_k
- max tokens
- benchmark task list
- git commit of this infra repo
