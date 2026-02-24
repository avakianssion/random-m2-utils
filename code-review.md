# Code Review Best Practices

## Purpose and standard - Why we do code review

Code review exists to ensure the overall code health improves over time, not just to find bugs.
“Code health” includes:

Correctness and reliability

Performance and resource efficiency

Operability (debuggability, observability, deployability)

Maintainability and clarity

The goal is to leave the codebase better than we found it.

## Approval

Approve when the change clearly improves overall code health, even if it is not perfect.
Do not block progress for polish-only issues; label those as nits.

If an issue affects correctness, performance, operability, or long-term maintainability, it is not a nit.

## Review speed expectations

We optimize for team throughput, not individual perfection.

Respond within 1 business day (even if only to acknowledge).

## What Should Code Reviewers Look For?

(Inspired by Google's best practices page.)
Design: Is the code well-designed and appropriate for your system?

Functionality: Does the code behave as the author likely intended? Is the way the code behaves good for its users?

Complexity: Could the code be made simpler? Would another developer be able to easily understand and use this code when they come across it in the future?

Tests: Does the code have correct and well-designed automated tests?

Naming: Did the developer choose clear names for variables, classes, methods, etc.?

Comments: Are the comments clear and useful?

Style: Does the code follow our style guides?

Documentation: Did the developer also update relevant documentation?
