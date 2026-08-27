# Architectural Decision Records (DECISIONS.md)

This document tracks all major architecture, evaluation, and security decisions made during the project.

## AD 001: Separation of Probabilistic and Deterministic Layers
**Date:** 2026-08-22
**Context:** Payment systems require strict security and determinism. LLMs are non-deterministic.
**Decision:** The LLM will strictly be used for diagnosis and generating natural language explanations. The actual decision to act (retry, fallback, escalate) will be handled by a strict, deterministic rule engine that takes the LLM's structured output and applies merchant-specific thresholds.

*Future decisions to be added here by Antigravity or Manus AI.*
