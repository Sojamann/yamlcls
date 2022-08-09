# Yamlcls
Allows recursive parsing of class instances from a yaml (dict).
Usage like dataclasses: generates \_\_init\_\_ and \_\_str\_\_.
Additionally yamlcls includes:
- automatic type checking
- handling of required arguments
- handling of optional arguments (setting defaults)
- custom mapping from yaml-name to python-instance-variable
- no external dependencies

## Get
```SH
wget https://raw.githubusercontent.com/Sojamann/yamlcls/v1.1.0/yamlcls.py
```

## Rules
- Everything needs to be type annotated, if you forget the type annotation
    unexpected happens
- Use Dict[.., ..] over dict or Dict
- Use List[..] over list or List
- Default values of members must be of type
    str, int, float, bool or a factory function
- Options

## Example
```PY
@yamlcls()
class A:
    a: int
    b: str

@yamlcls()
class B:
    a: A
    b: List[int]
    c: Dict[str, int]
    d: str = "Test"
    f: Any = yamlfield(alias="ffff", default=lambda: dict())

yamlstr = """
a:
   a: 1
   b: "B"
b: [1, 2]
c:
   test1: 1
   test2: 2
ffff:
-  a: 0
   b: 1
-  c: 0
   d: 1
"""
b = B(**yaml.safe_load(io.StringIO(yamlstr)))
b = B(yaml.safe_load(io.StringIO(yamlstr)))
print(str(b))
# B(a=A(a=1, b=B), b=[1, 2], c={'test1': 1, 'test2': 2}, f=[{'a': 0, 'b': 1}, {'c': 0, 'd': 1}], d=Test)
```

## Automatic type checking
### Wrong data type
```PY
@yamlcls()
class A:
    a: int

A(a="2")
# WrongType: Wrong type 'str' for key 'a'. Expected '<class 'int'>'.
```
### Missing required argument
```PY
@yamlcls()
class A:
    a: int

A()
# MissingRequiredArgument: Missing required argument 'a' for 'A'
```

### Unknown argument
```PY
@yamlcls()
class A:
    a: int

A(b=1)
# UnknownArgument: Unknown argument '1' of type 'int' with key 'b'.
```

### Wrong options
```PY
@yamlcls()
class A:
    a: int = yamlfield(options=["1", "2"])
# WrongType: Wrong type 'str' with value '1' for key 'Options of A.a'. Expected '<class 'int'>'.
```


