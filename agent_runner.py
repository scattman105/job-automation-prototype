# agent_runner.py
import asyncio
from agents import Agent, Runner, ComputerTool, AsyncComputer

agent = Agent(
    name="Test Computer Agent",
    instructions="Open a browser to https://openai.com and report the page title.",
    model="gpt-4.1-mini",
    tools=[ComputerTool(computer=AsyncComputer())]  # provide a computer backend
)

async def main():
    result = await Runner.run(agent, "Begin.")
    print(result.final_output)

if __name__ == "__main__":
    asyncio.run(main())