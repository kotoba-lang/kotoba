#!/usr/bin/env python3
r"""Crude Clojure-ish stripper: yields (lineno, code_line, raw_line) with ;comments removed and
string / regex-literal contents blanked (delimiters kept; regex literals tagged as #"...").
Char literals like \" \; \\ are handled. Multi-line strings keep state across lines."""
import sys, re

def strip_file(path):
    out = []
    in_str = False
    str_is_re = False
    with open(path, encoding='utf-8') as f:
        for ln, raw in enumerate(f, 1):
            line = raw.rstrip('\n')
            res = []
            i = 0
            n = len(line)
            while i < n:
                c = line[i]
                if in_str:
                    if c == '\\':
                        res.append('  ' if i + 1 < n else ' ')
                        i += 2
                        continue
                    if c == '"':
                        in_str = False
                        res.append('"')
                    else:
                        res.append(' ')
                    i += 1
                    continue
                if c == ';':
                    break
                if c == '\\' and i + 1 < n:
                    # char literal e.g. \" \; \a \newline
                    res.append('C')
                    i += 2
                    continue
                if c == '#' and i + 1 < n and line[i + 1] == '"':
                    in_str = True
                    str_is_re = True
                    res.append('#"')
                    i += 2
                    continue
                if c == '"':
                    in_str = True
                    str_is_re = False
                    res.append('"')
                    i += 1
                    continue
                res.append(c)
                i += 1
            out.append((ln, ''.join(res), raw))
    return out

if __name__ == '__main__':
    for ln, code, raw in strip_file(sys.argv[1]):
        print(ln, code)
