#!/usr/bin/env python3

# Exercise 19-B: Passcode Cracking

import collections
import sys

# Graph structure

Graph = collections.namedtuple('Graph', 'edges degrees')

# Read Graph

def read_graph():
    # TODO
    pass

# Topological Sort

def topological_sort(graph):
    # TODO
    pass

# Main Execution

def main():
    graph = read_graph()
    code  = topological_sort(graph)

    print(''.join(map(str, code)))

if __name__ == '__main__':
    main()
