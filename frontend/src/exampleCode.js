// Real, runnable code for each landing-page example chip.
//
// Previously, clicking a chip (or typing its label into the free-text
// prompt bar) turned the label into a Python COMMENT
// (`# Explain binary search`) rather than actual code -- there was no
// natural-language-to-code generation step anywhere in this pipeline,
// so the "narrated walkthrough" that resulted was essentially a blank
// video with only generic intro/outro narration. This file gives each
// of the three curated chips real source instead, so the promise the
// landing page makes ("paste code, get a narrated video") actually
// holds for the examples it advertises.
//
// This does NOT solve the free-text prompt bar's more fundamental gap:
// typing an arbitrary description still can't produce arbitrary code
// without an actual code-generation step (which would need an LLM call
// -- a bigger, separate feature decision involving cost and latency
// tradeoffs). See Root.jsx's handleLaunch for how free text that
// doesn't match one of these three labels is handled instead of being
// silently turned into a broken comment.
export const EXAMPLES = [
  {
    label: 'Explain binary search',
    code: `def binary_search(nums, target):
    low, high = 0, len(nums) - 1
    while low <= high:
        mid = (low + high) // 2
        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1

result = binary_search([1, 3, 5, 7, 9, 11, 13], 11)
print(result)  # Expected: 5
`,
  },
  {
    label: 'Show bubble sort',
    code: `def bubble_sort(nums):
    n = len(nums)
    for i in range(n):
        for j in range(0, n - i - 1):
            if nums[j] > nums[j + 1]:
                nums[j], nums[j + 1] = nums[j + 1], nums[j]
    return nums

result = bubble_sort([5, 2, 9, 1, 5, 6])
print(result)
`,
  },
  {
    label: 'Visualize BFS on a graph',
    code: `def bfs(graph, start):
    visited = [start]
    queue = [start]
    order = []
    while queue:
        node = queue.pop(0)
        order.append(node)
        for neighbor in graph[node]:
            if neighbor not in visited:
                visited.append(neighbor)
                queue.append(neighbor)
    return order

graph = {
    0: [1, 2],
    1: [0, 3],
    2: [0, 3],
    3: [1, 2],
}
result = bfs(graph, 0)
print(result)
`,
  },
];
