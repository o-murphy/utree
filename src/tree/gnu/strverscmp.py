def strverscmp(s1: str, s2: str) -> int:
    """
    Compares two strings lexicographically, treating contiguous sequences
    of digits as numbers.

    Returns a negative integer if s1 is less than s2, zero if they are
    equal, or a positive integer if s1 is greater than s2.
    """
    p1, p2 = 0, 0
    len1, len2 = len(s1), len(s2)

    while p1 < len1 and p2 < len2:
        c1, c2 = s1[p1], s2[p2]

        if c1.isdigit() and c2.isdigit():
            # Find the end of the digit sequences
            end1 = p1
            while end1 < len1 and s1[end1].isdigit():
                end1 += 1

            end2 = p2
            while end2 < len2 and s2[end2].isdigit():
                end2 += 1

            sub1 = s1[p1:end1]
            sub2 = s2[p2:end2]

            # Check for leading zeros
            is_fractional1 = len(sub1) > 1 and sub1.startswith('0')
            is_fractional2 = len(sub2) > 1 and sub2.startswith('0')

            if is_fractional1 and not is_fractional2:
                return -1
            if not is_fractional1 and is_fractional2:
                return 1

            num1 = int(sub1)
            num2 = int(sub2)

            if num1 != num2:
                return num1 - num2

            # If numbers are equal, compare their lengths
            if not is_fractional1 and not is_fractional2:
                if len(sub1) != len(sub2):
                    return len(sub1) - len(sub2)
            else:  # both are fractional
                if len(sub1) != len(sub2):
                    return len(sub2) - len(sub1)

            p1 = end1
            p2 = end2
            continue

        # Normal character comparison
        if c1 != c2:
            return ord(c1) - ord(c2)

        p1 += 1
        p2 += 1

    # Compare remaining parts of the strings
    return len1 - len2