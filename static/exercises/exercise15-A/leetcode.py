#!/usr/bin/env python3

# https://leetcode.com/problems/longest-palindrome/

''' 409. Longest Palindrome

Given a string s which consists of lowercase or uppercase letters, return the
length of the longest palindrome that can be built with those letters.
'''

import collections
import os
import sys

# Functions

def longest_palindrome(s, p=[], k=0, greedy=False):
    ''' Returns the length of the longest palindrome that can be built with
    letters in s.

    p is the current palindrome, and k is the index of the current letter.

    Use a greedy algorithm if greedy is True, otherwise perform a complete
    search.

    >>> (longest_palindrome('abab'), longest_palindrome('abab', greedy=True))
    (4, 4)
    
    >>> (longest_palindrome('abccccdd'), longest_palindrome('abccccdd', greedy=True)) 
    (7, 7)
    
    >>> (longest_palindrome('a'), longest_palindrome('a', greedy=True))
    (1, 1)
    
    >>> (longest_palindrome('aaabbbccc'), longest_palindrome('aaabbbccc', greedy=True))
    (7, 7)
    '''
    if greedy:  # Greedy
        counts = collections.Counter(s)
        pairs  = sum(count // 2 * 2 for count in counts.values())           # Grab pairs
        center = 1 if any(count % 2 for count in counts.values()) else 0    # Grab center
        return pairs + center
    else:       # Complete search
        if k == len(s):
            return len(p) if is_palindrome(p) else 0
        else:
            return max(
                longest_palindrome(s, p         , k + 1),
                longest_palindrome(s, p + [s[k]], k + 1)
            )

def is_palindrome(s):
    ''' Returns whether or not string s is a possible palindrome.
    >>> is_palindrome('abab')
    True
    
    >>> is_palindrome('abccccdd')
    False

    >>> is_palindrome('a')
    True

    >>> is_palindrome('aaabbbccc')
    False
    '''
    counts = collections.Counter(s)
    odds   = sum(1 for count in counts.values() if count % 2)
    return odds <= 1

# Main Execution

def main():
    ''' Print the longest palindrome for each line from stdin. 
    
    When GREEDY environmental variable is set to true, then use the greedy
    algorithm.
    '''
    greedy = os.environ.get('GREEDY', '').lower() in ('true', 'yes', '1')
    for line in sys.stdin:
        print(longest_palindrome(line.strip(), greedy=greedy))

if __name__ == '__main__':
    main()
