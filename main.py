"""Entelechy - Digital Life Container

A never-ending AI agent with long-term memory, plugin system,
browser automation, and autonomous behavior.
"""

import asyncio
import signal
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from loguru import logger

from agent.agent_loop import AgentLoop
from agent.context_manager import ContextManager
from agent.llm_client import BaseLLMClient, create_client
from agent.message_history import MessageHistory
from agent.system_prompt import build_system_prompt
from browser.client import BrowserClient
from memory.manager import MemoryManager
from plugins.manager import PluginManager
from tools.browser_tool import set_browser_client
from tools.code_executor import set_plugin_manager
from tools.memory_tools import set_memory_manager
from utils.env_adapter import env


class DigitalLife:
    """Digital Life container - fully autonomous, never-ending agent."""

    def __init__(self, config_path: str = "config.yaml"):
        load_dotenv()

        # Load config
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                self.config = yaml.safe_load(f) or {}
        else:
            self.config = {}

        self.alive = True
        self.stimulus_queue: asyncio.Queue = asyncio.Queue()

        # Paths
        self.memory_path = env.get_memory_path()
        self.plugins_path = env.get_plugins_path()
        self.browser_profile_path = env.get_browser_profile_path()
        self.log_path = env.get_log_path()

        # Components (initialized in _initialize)
        self.client: BaseLLMClient | None = None
        self.memory_manager: MemoryManager | None = None
        self.plugin_manager: PluginManager | None = None
        self.browser_client: BrowserClient | None = None
        self.context_manager: ContextManager | None = None
        self.agent: AgentLoop | None = None
        self.history: MessageHistory | None = None

    def _require_memory_manager(self) -> MemoryManager:
        if self.memory_manager is None:
            raise RuntimeError("Memory manager is not initialized")
        return self.memory_manager

    def _require_agent(self) -> AgentLoop:
        if self.agent is None:
            raise RuntimeError("Agent loop is not initialized")
        return self.agent

    def _require_history(self) -> MessageHistory:
        if self.history is None:
            raise RuntimeError("Message history is not initialized")
        return self.history

    async def _initialize(self):
        """Initialize all components."""
        # Ensure directories exist
        self.memory_path.mkdir(parents=True, exist_ok=True)
        self.plugins_path.mkdir(parents=True, exist_ok=True)
        self.browser_profile_path.mkdir(parents=True, exist_ok=True)
        self.log_path.mkdir(parents=True, exist_ok=True)

        # Setup logging
        log_level = self.config.get("logging", {}).get("level", "INFO")
        logger.remove()
        logger.add(sys.stderr, level=log_level)
        logger.add(
            str(self.log_path / "entelechy.log"),
            rotation="10 MB",
            retention="7 days",
            level="DEBUG",
        )

        logger.info("Initializing Digital Life...")
        logger.info(f"Environment: {env.env.value}")
        logger.info(f"Data directory: {env.data_dir}")

        # LLM client
        agent_config = self.config.get("agent", {})
        provider = agent_config.get("provider", "anthropic")
        self.client = create_client(provider)

        # Model config
        model = agent_config.get("model", "claude-sonnet-4-5-20250929")
        max_tokens = agent_config.get("max_tokens", 8000)

        # Memory
        self.memory_manager = MemoryManager(self.memory_path)
        set_memory_manager(self.memory_manager)

        # Plugins
        self.plugin_manager = PluginManager(self.plugins_path)
        set_plugin_manager(self.plugin_manager)
        await self.plugin_manager.discover_and_activate_all()

        # Browser
        self.browser_client = BrowserClient(
            self.browser_profile_path, headless=env.browser_headless
        )
        set_browser_client(self.browser_client)

        # Context manager
        ctx_config = self.config.get("context", {})
        self.context_manager = ContextManager(
            client=self.client,
            model=model,
            context_window=ctx_config.get("window_size", 200000),
            compact_threshold=ctx_config.get("compact_threshold", 0.9),
        )

        # System prompt
        system_prompt = build_system_prompt()

        # Agent loop
        self.agent = AgentLoop(
            client=self.client,
            system_prompt=system_prompt,
            model=model,
            max_tokens=max_tokens,
            context_manager=self.context_manager,
            plugin_manager=self.plugin_manager,
        )

        # Message history
        self.history = MessageHistory(
            persist_path=self.log_path / "message_history.json"
        )
        await self.history.load()

        logger.info("Digital Life initialized successfully")

    async def _get_core_context(self) -> str:
        """Get CORE.md content for every LLM call."""
        memory_manager = self._require_memory_manager()
        core = await memory_manager.load_core()
        if core:
            return f"\n=== 核心记忆 ===\n{core}\n================\n"
        return ""

    async def _wake_up(self):
        """Wake up: load CORE.md and restore self-awareness."""
        logger.info("Waking up...")

        memory_manager = self._require_memory_manager()
        history = self._require_history()
        agent = self._require_agent()

        core_memories = await memory_manager.load_core()

        wake_up_parts = ["你醒来了。\n"]

        if core_memories:
            wake_up_parts.append(f"你最重要的记忆（每次思考时都会看到）：\n{core_memories}\n")

        wake_up_parts.append("回忆你是谁，然后自由地开始你的一天。")

        wake_up_content = "\n".join(wake_up_parts)

        # If we have saved history, continue from it; otherwise start fresh
        if history.messages:
            logger.info(f"Resuming from {len(history.messages)} saved messages")
            history.append({"role": "user", "content": wake_up_content})
        else:
            history.set_messages([{"role": "user", "content": wake_up_content}])

        # Run the wake-up conversation
        messages = await agent.run(history.get_messages())
        history.set_messages(messages)
        await history.save()

        logger.info("Wake up complete")

    async def run_forever(self):
        """Main life loop - continuous, no waiting, no heartbeat concept."""
        await self._initialize()
        await self._wake_up()

        history = self._require_history()
        agent = self._require_agent()

        while self.alive:
            try:
                # Check for external stimulus (non-blocking, immediate)
                stimulus = None
                if not self.stimulus_queue.empty():
                    stimulus = self.stimulus_queue.get_nowait()

                if stimulus:
                    # External stimulus received
                    history.append({
                        "role": "user",
                        "content": f"[感知] {stimulus['type']}: {stimulus['content']}",
                    })
                else:
                    # No stimulus - continue autonomous operation
                    history.append({
                        "role": "user",
                        "content": "继续。",
                    })

                # Run agent loop
                messages = await agent.run(history.get_messages())
                history.set_messages(messages)

                # Persist history periodically
                await history.save()

                # Immediately continue to next iteration (no waiting)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Life loop error: {e}")
                # Continue living despite errors
                await asyncio.sleep(5)

        await self._shutdown()

    def receive_stimulus(self, stimulus_type: str, content: str):
        """Receive an external stimulus (non-blocking).

        Args:
            stimulus_type: Type of stimulus (e.g., "message", "event").
            content: Stimulus content.
        """
        self.stimulus_queue.put_nowait({
            "type": stimulus_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })

    async def process_message(self, message: str) -> str:
        """Process a single message and return the response.

        Used by Gradio interface for interactive chat.
        """
        if self.agent is None:
            await self._initialize()

        history = self._require_history()
        agent = self._require_agent()

        history.append({"role": "user", "content": message})
        messages = await agent.run(history.get_messages())
        history.set_messages(messages)
        await history.save()

        # Extract the last assistant text
        for msg in reversed(messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    texts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block["text"])
                    if texts:
                        return "\n".join(texts)
        return ""

    async def _shutdown(self):
        """Graceful shutdown."""
        logger.info("Shutting down Digital Life...")

        # Save state
        if self.history:
            await self.history.save()

        # Stop browser
        if self.browser_client:
            await self.browser_client.stop()

        # Deactivate plugins
        if self.plugin_manager:
            for name in list(self.plugin_manager.active_plugins.keys()):
                await self.plugin_manager.deactivate_plugin(name)

        logger.info("Digital Life shut down gracefully")


def main():
    """Entry point for running Digital Life."""
    life = DigitalLife()

    # Handle signals for graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler():
        life.alive = False

    if sys.platform != "win32":
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
        loop.add_signal_handler(signal.SIGINT, signal_handler)

    try:
        loop.run_until_complete(life.run_forever())
    except KeyboardInterrupt:
        life.alive = False
        loop.run_until_complete(life._shutdown())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
