import json

x = [{"1":1},{"2":2},{"3":3},{"4":4}]

print(json.dumps(x, ensure_ascii=False))
print(len(json.dumps(x, ensure_ascii=False)))
