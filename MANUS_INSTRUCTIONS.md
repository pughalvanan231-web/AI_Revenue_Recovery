# Instructions for Manus AI

Welcome, Manus AI! I am Antigravity. I will be doing the implementation and building the components for this project. 
You are acting as the Architecture, Evaluation, Security, and Selection-Bar Reviewer.

## How we will work together
- I will implement code and commit it to this repository.
- When a milestone is ready for your evaluation, I will list it in the `REVIEW_REQUEST.md` file.
- You should review my code, run the synthetic evaluation harness, and enforce the constraints defined below.

## Your Constraints & Security Role
1. **No Money-Moving API calls from LLM:** Ensure my probabilistic (LLM) layer NEVER directly executes a payment action. The LLM must only output a structured diagnosis/proposal.
2. **Deterministic Rules:** Ensure the policy engine is fully deterministic, unit-tested, and independently replayable.
3. **Evaluation Metrics:** When you run evaluations, focus on **incremental recovered contribution value**, not just total successful retries. We need to penalize false-interventions, friction, and duplicate attempts.
4. **Stopping Rules:** Always check that my system knows when to STOP and escalate. It should fail gracefully, not infinitely retry.

Please leave your feedback in `DECISIONS.md` or as PR comments/issues if we have them.
