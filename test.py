import io
import yaml

from yamlcls import yamlcls, yamlfield, asdict
from typing import Any, Dict, List

# ONE SHOULD USE DIFFERENT METHODS THROUGHOUT THE TESTS
# @yamlcls AND @yamlcls()
# a = A({}) AND a = A(**{})

def raises(callable):
    try:
        callable()
        raise Exception("Expected code to raise an Exception")
    except Exception as e:
        return

def raises_for_type(t):
    try:
        @yamlcls
        class _:
            a: t
        raise Exception(f"Expected: type {t} not to be allowed")
    except:
        return


def raises_for_default(t, default):
    try:
        @yamlcls
        class _:
           a: t = default
        raise Exception(f"Expected: default {type(t)} not to be allowed")
    except:
        return


def ok_for_type(t):
    @yamlcls
    class _:
        a: t

def ok_for_default(t, default):
    @yamlcls
    class _:
        a: t = default

def test_type_validation():
    class ExampleCls:
        a: int

    raises_for_type(list)
    raises_for_type(dict)
    raises_for_type(List)
    raises_for_type(Dict)
    raises_for_type(Dict[bool, str])
    raises_for_type(List[list])
    raises_for_type(Dict[dict, list])
    raises_for_type(Dict[List[str], int])
    raises_for_type(Dict[List[str], List[str]])

    raises_for_default(int, [])
    raises_for_default(int, {})
    raises_for_default(int, "")
    raises_for_default(int, 2.2)
    raises_for_default(str, 2)
    raises_for_default(str, 2.2)
    raises_for_default(str, True)

    ok_for_default(Any, 2)
    ok_for_default(Any, "")
    ok_for_default(Any, dict)
    ok_for_default(Any, True)
    ok_for_default(Any, 2.2)
    ok_for_default(int, 2)
    ok_for_default(float, 2.2)
    ok_for_default(str, "2")
    ok_for_default(bool, False)
    ok_for_default(Dict[Any, Any], lambda: dict())
    ok_for_default(Dict[int, int], lambda: dict({1:2}))
    ok_for_default(int, None)

    ok_for_type(int)
    ok_for_type(float)
    ok_for_type(str)
    ok_for_type(bool)
    ok_for_type(ExampleCls)
    ok_for_type(List[str])
    ok_for_type(List[int])
    ok_for_type(List[float])
    ok_for_type(List[bool])
    ok_for_type(List[List[str]])
    ok_for_type(List[Dict[str, str]])

    ok_for_type(Dict[str, int])
    ok_for_type(Dict[int, float])
    ok_for_type(Dict[float, bool])
    ok_for_type(Dict[int, Dict[str, int]])
    ok_for_type(Dict[str, List[List[str]]])

    ok_for_type(Any)

def test_primitive_loading():
    @yamlcls
    class A:
        a: int
        b: str
        c: float
        d: bool

    a_yaml = """
                a: 1
                b: "1"
                c: 1.1
                d: false
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(**d)

    assert a.a == 1
    assert a.b == "1"
    assert a.c == 1.1
    assert a.d == False

    @yamlcls
    class A:
        a: int = 1
        b: str = "1"
        c: float = 1.1
        d: bool = False

    d = {}
    a = A(**d)

    assert a.a == 1
    assert a.b == "1"
    assert a.c == 1.1
    assert a.d == False

    @yamlcls
    class A:
        a: int
        b: str
        c: float = 1.1
        d: bool = False

    a_yaml = """
                a: 1
                b: "1"
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(**d)

    assert a.a == 1
    assert a.b == "1"
    assert a.c == 1.1
    assert a.d == False

def test_list_and_dict():
    @yamlcls
    class A:
        a: List[int]
        b: Dict[str, int]

    a_yaml = """
                a: [1, 2, 3]
                b:
                    inner: 1
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(**d)

    assert a.a == [1, 2, 3]
    assert a.b == {"inner": 1}

def test_nested_list_and_dict():
    @yamlcls
    class A:
        a: List[List[int]]
        b: List[Dict[int, int]]
        c: Dict[str, int]
        d: Dict[str, List[int]]

    a_yaml = """
                a: [[1, 2, 3]]
                b:
                - 1: 1
                - 2: 2
                c:
                    a: 1
                    b: 2
                d:
                    a: [1, 2]
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(d)

    assert a.a == [[1, 2, 3]]
    assert a.b == [{1: 1}, {2: 2}]
    assert a.c == {"a": 1, "b": 2}
    assert a.d == {"a": [1, 2]}

def test_class():
    @yamlcls
    class B:
        a: int
    @yamlcls
    class A:
        b: B

    a_yaml = """
                b:
                    a: 1
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(d)

    assert a.b.a == 1

    class B:
        def __init__(self, a: int):
            self.a = a
    @yamlcls
    class A:
        b: B

    a_yaml = """
                b:
                    a: 1
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(**d)

    assert a.b.a == 1

    @yamlcls()
    class C:
        a: int
    @yamlcls()
    class B:
        c: C
    @yamlcls()
    class A:
        b: B

    a_yaml = """
                b:
                    c:
                        a: 1
            """
    d = yaml.safe_load(io.StringIO(a_yaml))
    a = A(**d)

    assert a.b.c.a == 1

def init_methods():
    @yamlcls
    class A:
        a: int
        b: int

    d = {"a": 1, "b": 2}

    a1 = asdict(A(d))
    a2 = asdict(A(**d))
    assert a1 == a2

def test_str():
    @yamlcls()
    class A:
        a: int = 1
        b: str = "a"

    a = A(a = 1)
    assert len(str(a)) > 0

def test_any():
    @yamlcls()
    class A:
        a: int
        b: Any

    d = {"a": 1, "b": 0}
    a = A(d)
    assert a.a == d["a"]
    assert a.b == d["b"]

    d = {"a": 1, "b": [11111, 1111]}
    a = A(d)
    assert a.a == d["a"]
    assert a.b == d["b"]

    d = {"a": 1, "b": ""}
    a = A(d)
    assert a.a == d["a"]
    assert a.b == d["b"]

def test_default_factory_function():
    @yamlcls
    class A:
        a: Dict[int, int] = lambda: dict({"a": "a"})
    raises(A)

    @yamlcls
    class A:
        a: Dict[int, int] = lambda: dict({"a": 1})
    raises(A)

    @yamlcls
    class A:
        a: Dict[Any, Any] = lambda: dict({"a": 1})
    A()


def test_yamlfield():
    # alias testing
    @yamlcls()
    class A:
        a: int = yamlfield(alias="other")

    a = A({"other": 22})
    assert a.a == 22

    @yamlcls()
    class A:
        a: int = yamlfield(alias="a-b")
    a = A({"a-b": 22})
    assert a.a == 22

    @yamlcls()
    class A:
        a: int = yamlfield(alias="a-b")

    yamlstr = """
    a-b: 2
    """

    a = A(yaml.safe_load(io.StringIO(yamlstr)))
    assert a.a == 2
    a = A(**yaml.safe_load(io.StringIO(yamlstr)))
    assert a.a == 2

    # default testing
    @yamlcls
    class A:
        i: int = yamlfield(default=222)

    a = A({})
    assert a.i == 222

    # alias & default testing
    @yamlcls
    class A:
        i: int = yamlfield(alias="BB", default=222)

    a = A({})
    assert a.i == 222

def test_ignore_unknown():
    @yamlcls(ignore_unknown=True)
    class A:
        a: int

    a = A({"a": 2, "b": 3})
    assert a.a == 2
    assert not hasattr(a, "b")

    @yamlcls(ignore_unknown=False)
    class A:
        a: int
    raises(lambda: A({"a": 2, "b": 3}))

def test_ignore_missing():
    @yamlcls(ignore_missing=True)
    class A:
        a: int
        b: int

    a = A({"a": 2})
    assert a.a == 2
    assert not hasattr(a, "b")


    @yamlcls(ignore_missing=False)
    class A:
        a: int
        b: int

    raises(lambda: A({"a": 2}))

def test_options():
    @yamlcls()
    class A:
        a: int = yamlfield(options = [1, 2])

    raises(lambda: A(a=3))
    raises(lambda: A(a='22'))
    A(a=2)

    @yamlcls()
    class A:
        a: List[int] = yamlfield(options = [[1, 2]])

    raises(lambda: A(a=3))
    A(a=[1, 2])

    raises_for_default(int, yamlfield(options=["s", "b"]))
    ok_for_default(List[str], yamlfield(options=[["s"], ["b"]]))

if __name__ == "__main__":
    test_type_validation()
    test_primitive_loading()
    test_list_and_dict()
    test_nested_list_and_dict()
    test_class()
    init_methods()
    test_str()
    test_any()
    test_default_factory_function()
    test_yamlfield()
    test_ignore_unknown()
    test_ignore_missing()
    test_options()
