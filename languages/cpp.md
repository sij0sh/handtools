# C++ profile

Top rule: Make resource ownership and borrowed lifetimes explicit.

## 1 Structure

- Default: group APIs by capability; no mandatory directory or target per capability.
- Default: keep private headers private and expose small value-oriented APIs.
- Heuristic: split libraries/targets for real consumer or build boundaries.

## 2 Preferred

- Default: use the repository-supported stable standard; C++20 is the conservative fallback.
- Requirement: use RAII for owned resources, including failure paths.
- Default: use values and `std::unique_ptr` for exclusive dynamic ownership.
- Requirement: make `std::span`/`std::string_view` borrowing lifetimes explicit;
  views must not outlive backing storage or survive invalidating mutations.
- Default: use `std::optional` for absence and tagged values for business outcomes.
- Default: use exceptions for operational failures; exception-free targets use
  explicit result/status types consistently, not unchecked success assumptions.
- Default: synchronous calls first; concurrency only for demonstrated need.
- Requirement: own tasks/threads, cancel or request stop, join, and observe failures.
- Default: use `enum class`, `constexpr`, and meaningful `[[nodiscard]]` results.

## 3 Disallowed

- Default: avoid owning raw pointers; isolate low-level allocation adapters.
- Requirement: no dangling views, uninitialized values, or unchecked size arithmetic.
- Default: avoid C-style casts, macro control flow, and `using namespace` in headers.
