def test_function(x):
    if x > 0:
        return 1
    else:
        return 0

def loop_example(items):
    result = []
    for item in items:
        if item > 5:
            result.append(item)
    return result

def while_example(n):
    i = 0
    while i < n:
        i += 1
    return i

