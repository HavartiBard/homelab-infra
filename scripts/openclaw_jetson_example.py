#!/usr/bin/env python3
"""
OpenClaw + Jetson Ollama Integration Example

Demonstrates how to use Jetson-hosted Ollama models for agent reasoning.
This is a reference implementation for OpenClaw integration.

Usage:
    python scripts/openclaw_jetson_example.py --task reasoning
    python scripts/openclaw_jetson_example.py --task coding
    python scripts/openclaw_jetson_example.py --task auto

Requirements:
    pip install openai requests
"""

import argparse
import time
from typing import Literal
from openai import OpenAI


# Jetson Ollama endpoint configuration
JETSON_ENDPOINT = "http://192.168.20.169:11434/v1"
LLAMA_MODEL = "llama3.1:8b-instruct-q4_K_M"
QWEN_MODEL = "qwen2.5-coder:7b-instruct-q4_K_M"


class JetsonAgent:
    """
    OpenClaw-style agent using Jetson Ollama for reasoning.

    Provides intelligent model selection and performance monitoring.
    """

    def __init__(
        self,
        model: str | None = None,
        reasoning_budget: int = 2000,
        stream: bool = False
    ):
        """
        Initialize Jetson agent.

        Args:
            model: Model to use (or None for auto-selection)
            reasoning_budget: Max tokens for reasoning (not enforced by Ollama)
            stream: Enable streaming responses
        """
        self.client = OpenAI(
            base_url=JETSON_ENDPOINT,
            api_key="ollama"  # Required but not validated
        )
        self.default_model = model
        self.reasoning_budget = reasoning_budget
        self.stream = stream
        self.stats = {
            "total_requests": 0,
            "total_tokens": 0,
            "total_time": 0.0
        }

    def select_model(self, task_type: Literal["reasoning", "code", "auto"]) -> str:
        """
        Select optimal model based on task type.

        Args:
            task_type: Type of task (reasoning, code, or auto)

        Returns:
            Model name to use
        """
        if self.default_model:
            return self.default_model

        if task_type == "code":
            return QWEN_MODEL
        elif task_type == "reasoning":
            return LLAMA_MODEL
        else:  # auto
            return LLAMA_MODEL  # Default to Llama for general tasks

    def reason(
        self,
        prompt: str,
        task_type: Literal["reasoning", "code", "auto"] = "auto",
        system_message: str | None = None
    ) -> str:
        """
        Execute reasoning task with appropriate model.

        Args:
            prompt: User prompt
            task_type: Task type for model selection
            system_message: Optional system message

        Returns:
            Model response
        """
        model = self.select_model(task_type)

        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        print(f"\n{'='*60}")
        print(f"Model: {model}")
        print(f"Task: {task_type}")
        print(f"Prompt: {prompt[:80]}...")
        print(f"{'='*60}\n")

        start_time = time.time()

        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            stream=self.stream
        )

        if self.stream:
            # Handle streaming response
            full_response = ""
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)
                    full_response += content
            print("\n")
            result = full_response
        else:
            result = response.choices[0].message.content
            print(result)
            print()

        elapsed = time.time() - start_time

        # Update stats
        self.stats["total_requests"] += 1
        self.stats["total_time"] += elapsed

        # Estimate tokens (rough approximation)
        estimated_tokens = len(result.split())
        self.stats["total_tokens"] += estimated_tokens

        print(f"{'='*60}")
        print(f"Time: {elapsed:.2f}s")
        print(f"Est. tokens: {estimated_tokens}")
        print(f"Est. speed: {estimated_tokens/elapsed:.2f} tokens/sec")
        print(f"{'='*60}\n")

        return result

    def get_stats(self) -> dict:
        """Get performance statistics."""
        avg_time = self.stats["total_time"] / max(self.stats["total_requests"], 1)
        avg_speed = self.stats["total_tokens"] / max(self.stats["total_time"], 1)

        return {
            **self.stats,
            "avg_time_per_request": avg_time,
            "avg_tokens_per_sec": avg_speed
        }


def demo_reasoning():
    """Demonstrate reasoning capabilities with Llama 3.1."""
    agent = JetsonAgent()

    print("\n" + "="*60)
    print("DEMO: Reasoning with Llama 3.1 8B")
    print("="*60)

    # Test 1: Mathematical reasoning
    agent.reason(
        "Think step-by-step: A store has 15 apples. They sell 7 apples and receive "
        "a shipment of 23 more apples. How many apples does the store have now?",
        task_type="reasoning",
        system_message="You are a helpful assistant that thinks step-by-step."
    )

    # Test 2: Logical reasoning
    agent.reason(
        "If all mammals are warm-blooded, and all whales are mammals, "
        "what can we conclude about whales? Explain your reasoning.",
        task_type="reasoning"
    )

    stats = agent.get_stats()
    print("\nSession Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Avg time: {stats['avg_time_per_request']:.2f}s")
    print(f"  Avg speed: {stats['avg_tokens_per_sec']:.2f} tokens/sec")


def demo_coding():
    """Demonstrate code generation with Qwen 2.5 Coder."""
    agent = JetsonAgent()

    print("\n" + "="*60)
    print("DEMO: Code Generation with Qwen 2.5 Coder")
    print("="*60)

    # Test 1: Function generation
    agent.reason(
        "Write a Python function that takes a list of numbers and returns "
        "the median value. Include a docstring and handle edge cases.",
        task_type="code",
        system_message="You are an expert Python programmer."
    )

    # Test 2: Algorithm implementation
    agent.reason(
        "Implement a binary search function in Python with type hints. "
        "Include docstring with complexity analysis.",
        task_type="code"
    )

    stats = agent.get_stats()
    print("\nSession Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Avg time: {stats['avg_time_per_request']:.2f}s")
    print(f"  Avg speed: {stats['avg_tokens_per_sec']:.2f} tokens/sec")


def demo_auto_routing():
    """Demonstrate automatic model selection based on task type."""
    agent = JetsonAgent()

    print("\n" + "="*60)
    print("DEMO: Auto Model Selection")
    print("="*60)

    # This should route to Qwen (code keywords detected)
    agent.reason(
        "Write a Python function to calculate fibonacci numbers recursively.",
        task_type="code"
    )

    # This should route to Llama (general reasoning)
    agent.reason(
        "Explain the concept of recursion in simple terms.",
        task_type="reasoning"
    )

    # Auto selection (will use Llama by default)
    agent.reason(
        "What are the key differences between Python and JavaScript?",
        task_type="auto"
    )

    stats = agent.get_stats()
    print("\nSession Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Avg time: {stats['avg_time_per_request']:.2f}s")
    print(f"  Avg speed: {stats['avg_tokens_per_sec']:.2f} tokens/sec")


def main():
    """Run demonstration based on command-line arguments."""
    parser = argparse.ArgumentParser(
        description="OpenClaw + Jetson Ollama Integration Example"
    )
    parser.add_argument(
        "--task",
        choices=["reasoning", "coding", "auto", "all"],
        default="all",
        help="Which demo to run (default: all)"
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Enable streaming responses"
    )

    args = parser.parse_args()

    print("\n" + "="*60)
    print("OpenClaw + Jetson Ollama Integration")
    print("="*60)
    print(f"Endpoint: {JETSON_ENDPOINT}")
    print(f"Llama Model: {LLAMA_MODEL}")
    print(f"Qwen Model: {QWEN_MODEL}")
    print(f"Streaming: {'Enabled' if args.stream else 'Disabled'}")
    print("="*60)

    if args.task == "all":
        demo_reasoning()
        demo_coding()
        demo_auto_routing()
    elif args.task == "reasoning":
        demo_reasoning()
    elif args.task == "coding":
        demo_coding()
    elif args.task == "auto":
        demo_auto_routing()

    print("\n" + "="*60)
    print("Integration demo complete!")
    print("="*60)
    print("\nNext steps:")
    print("  1. Adapt this code for your OpenClaw agents")
    print("  2. Implement task-specific system messages")
    print("  3. Add error handling and retry logic")
    print("  4. Monitor performance in production")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
