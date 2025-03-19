from collections import deque

# Node structure
class Node:
    def __init__(self, value, left=None, right=None):
        self.value = value
        self.left = left
        self.right = right

# Pre-defined Trees
def algorithm_tree():
    return Node('A',
        Node('L',
            Node('O',
                Node('H'),
                Node('M')
            ),
            Node('R')
        ),
        Node('G',
            Node('I'),
            Node('T')
        )
    )

def wikipedia_tree():
    return Node('F',
        Node('B',
            Node('A'),
            Node('D',
                Node('C'),
                Node('E')
            )
        ),
        Node('G',
            None,
            Node('I',
                Node('H'),
                None
            )
        )
    )

def reading02_tree():
    return Node('W',
        Node('Y',
            Node('D',
                Node('F'),
                Node('U')
            ),
            Node('B',
                Node('L'),
                Node('A')
            )
        ),
        Node('R',
            Node('I',
                Node('R'),
                Node('A')
            ),
            Node('O',
                Node('E'),
                Node('D')
            )
        )
    )

# Traversals
def bfs(root):
    pass

def dfs(root):
    pass

def dfs_recursive(root):
    pass

if __name__ == "__main__":
    tree = algorithm_tree()
    # tree = wikipedia_tree()
    # tree = reading02_tree()

    print("BFS:", end=" ")
    bfs(tree)
    print("DFS:", end=" ")
    dfs(tree)
    print("DFS Recursive:", end=" ")
    dfs_recursive(tree)
    print()