import sys
import json
from typing import List, Tuple, Dict
from collections import defaultdict, deque

def maxMonkeys(vines: List[List[str]]) -> int:
    """
    Calculate the maximum number of monkeys that can sit on sturdy vines
    without being able to throw bananas at each other.
    """

    rows, cols = len(vines), len(vines[0])

    # Create a graph representing all possible monkey placements and banana-throwing conflicts
    jungleGraph: Dict[Tuple[int, int], Dict[Tuple[int, int], int]] = defaultdict(dict)
    total_monkey_spots = 0

    # Special nodes to act as source (entry) and sink (exit) for flow simulation
    tree_entry = (-1, -1)
    tree_exit = (rows, cols)

    # 🐾 TODO 1: Add edges from tree_entry to all valid monkey spots on even-numbered columns
    # For each spot (r, c) that is '.', and c is even:
    #   - Connect tree_entry -> (r, c) with capacity 1
    #   - For each banana-throwing neighbor (diagonals and sides),
    #     if it's also '.', connect (r, c) -> neighbor with capacity 1
    #   - Also add reverse edges with capacity 0
    #   - Keep track of how many monkeys could potentially sit in total

    # 🐾 TODO 2: Add edges from valid monkey spots on odd-numbered columns to tree_exit
    # For each spot (r, c) that is '.', and c is odd:
    #   - Connect (r, c) -> tree_exit with capacity 1
    #   - Also add reverse edge with capacity 0
    #   - Increase total_monkey_spots count

    # 🍌 TODO 3: Implement a BFS function that:
    #   - Finds a path from tree_entry to tree_exit (ignoring 0-capacity edges)
    #   - If a path exists, updates the residual graph along that path
    #   - Returns True if a path was found (and flow added), False otherwise

    # 🧮 TODO 4: Use the BFS function in a loop to count how many banana-throwing conflicts
    # (i.e., how many times monkeys would clash and must be separated)

    # 🎉 TODO 5: Return the number of monkeys that can sit safely:
    # (total_monkey_spots - number_of_conflicts)

    return -1  # Placeholder until you implement the logic

# --- Main I/O Logic ---
def main():
    lines = [line.strip() for line in sys.stdin if line.strip()]
    num_cases = int(lines[0])
    for i in range(1, num_cases + 1):
        vines = json.loads(lines[i])  # List[List[str]]
        result = maxMonkeys(vines)
        print(result)

if __name__ == "__main__":
    main()