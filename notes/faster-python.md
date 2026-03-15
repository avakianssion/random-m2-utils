# Faster Python Notes

## Loop-Invariant Statements

A loop-invariant statement is any computation inside a loop that produces the same result on every iteration. Leaving these inside the loop wastes CPU cycles and slows down hot paths.

Example (inefficient):

```python
for item in items:
    pattern_re = re.compile(PATTERN)  # doesn’t depend on `item`
    if pattern_re.search(item):
        ...
```

Better (hoisted outside the loop):

```python
pattern_re = re.compile(PATTERN)
for item in items:
    if pattern_re.search(item):
        ...
```

When to hoist: regex compilation, constant expressions, config lookups, expensive object creation—anything that does not depend on the loop variable.

1. Utilize Comprehensions

Python comprehensions (list, set, dict) are faster and cleaner than manually building collections inside a loop. They reduce bytecode overhead and keep logic compact.

Example (Inefficient)

```python
result = []
for x in items:
    if x.is_valid():
        result.append(transform(x))
```

Better

```python
result = [transform(x) for x in items if x.is_valid()]
```

## Comprehensions

### List comprehensions to build lists

- Set comprehensions for deduplication / fast membership
- Dict comprehensions for transforming mappings
- If the pattern is “iterate → filter → transform → collect,” a comprehension is usually the best tool.

## Selecting the Right Data Structures

### Choosing the correct data structure often provides the biggest performance payoff.

#### list

Best for: ordered data, sequential iteration
Avoid for: frequent x in list checks (O(n))

#### set

Best for: fast membership tests (O(1)), uniqueness
Use when repeatedly checking “have we seen this?”

#### dict

Best for: key/value lookups, counts, indexed operations
Prefer over scanning lists of tuples for matches

#### deque (from collections)

Best for: fast appends/pops from both ends
Prefer over list.pop(0) which is slow

### Avoid Tiny Functions in Hot Areas of Code

Python has noticeable overhead per function call. In hot loops or high-frequency code paths, calling small “trivial” functions can significantly slow execution.

Example:

```python
def add_one(x):
    return x + 1

for i in range(1_000_000):
    total += add_one(i)   # millions of function calls
```

Inline version (faster):

```python
for i in range(1_000_000):
    total += i + 1
```

This doesn’t mean “never use small functions”—clarity comes first.
