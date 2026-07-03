with open('/home/noufan/Desktop/Learning/ROTECH/projects/E_Voting_V2/voting/templates/voting/results.html', 'r') as f:
    lines = f.readlines()

div_stack = []
for i, line in enumerate(lines, 1):
    # Find all <div or </div
    # This is a naive check but can help find mismatches
    import re
    tokens = re.findall(r'<div|</div', line)
    for token in tokens:
        if token == '<div':
            div_stack.append(i)
        elif token == '</div':
            if div_stack:
                div_stack.pop()
            else:
                print(f"Extra closing div on line {i}")

print(f"Unclosed divs at end: {len(div_stack)} starting at lines {div_stack}")
