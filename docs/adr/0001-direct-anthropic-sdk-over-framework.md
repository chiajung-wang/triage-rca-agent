# ADR 0001: Direct Anthropic SDK over LangChain/LangGraph

## Status
Accepted

## Context
Building a multi-agent orchestrator requires a framework decision. LangGraph is the dominant choice in the ecosystem and handles graph structure, state management, and routing out of the box. The Anthropic SDK is a thin HTTP client with no agentic scaffolding.

## Decision
Use the Anthropic SDK directly. Build the orchestrator loop, state management, retry hierarchy, and subagent dispatch as custom code (~hundreds of lines).

## Consequences
- Every agentic pattern (budget tracking, recovery levels, subagent dispatch) is visible in the codebase and explainable in interviews
- LangGraph handles these for free — this is deliberate extra work
- Portfolio differentiator: most agent projects use LangGraph; owning the loop is uncommon
- Tradeoff: no free checkpointing, no built-in streaming graph UI, more code to maintain
- Defensible answer: "I evaluated LangGraph, understood what it abstracts, and chose to own those abstractions to demonstrate systems understanding"
