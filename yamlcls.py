import abc
import itertools
import inspect
from typing import Any, Callable, Dict, List, Union, Type


########################
# Helper Types
#########################
NoneType = type(None)
# all types which as primitives do not require any recursive type resolution
PRIMITIVES = (str, int, float, bool)
# all types which are allowed to be used for dictionary keys
ALLOWED_DICT_KEY_TYPES = (str, int, float)
# all types which are allowed to be used as type annotations
ALLOWED_TYPE_ANNOTATIONS = (str, int, float, bool, dict, list, type, Any)
# all types which are allowed to be default types for members.
# this should be kept in sync with DefaultVarType
VAR_DEFAULT_TYPES = (str, int, float, bool, Callable, NoneType)

# internal type hint for what a default can be
# class A:
#   i: int = 1
#   f: float = 1.1
#   b: bool = False
#   s: str = "Test"
#   d: Dict[int, int] = dict
#   special: Dict[str, str] = lambda: dict({1: 1})
DefaultVarType = Union[Callable, str, int, float, bool, NoneType]


class RequiredVar:
    def __init__(self, type: Type):
        self.type = type

class OptionalVar:
    def __init__(self, type: Type, default: DefaultVarType):
        self.type = type
        self.default = default

class YamlField:
    def __init__(self,
                 alias: str = None,
                 default: DefaultVarType = None,
                 options: List = None):
        self.alias = alias
        self.default = default
        self.options = options

class Resolver(abc.ABC):
    @abc.abstractmethod
    def is_responsible(self, value: Any, target: Type) -> bool:
        pass

    @abc.abstractmethod
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        pass

#########################
# Helpers
#########################
def get_annotations(vtype: Type):
    return vtype.__dict__.get("__annotations__", {}).items()

def generic_of(vtype: Type):
    """ List[..]        => list """
    """ Dict[.., ..]    => dict """
    return getattr(vtype, "__origin__", None)

def generic_over(vtype: Type):
    """ List[int]        => [int] """
    """ Dict[int, int]   => [int, int] """
    return getattr(vtype, "__args__", None)

def is_generic_list(vtype: Type):
    """ Check that List[..] """
    return generic_of(vtype) == list and len(generic_over(vtype)) == 1

def is_generic_dict(vtype: Type):
    """ Check that Dict[.., ..] """
    return generic_of(vtype) == dict and len(generic_over(vtype)) == 2

def assert_type_annotation_allowed(name: str, vtype: Type):
    """
    This function checks weather the type is allowed for eg. a class like:
    class A:
        name: vtype
    """
    if vtype in PRIMITIVES or vtype == Any:
        return

    # no untyped list and dicts because we cannot check them
    if vtype in [dict, list]:
        raise Exception(f"Cannot use untyped list or dict '{name}'")
    if generic_of(vtype) in [list, dict] and generic_over(vtype) == None:
        raise Exception(f"Cannot used untyped List or Dict. Please add type hint(s)")

    # List[..] might be nested
    if generic_of(vtype) == list:
        assert_type_annotation_allowed(name, generic_over(vtype)[0])
        return

    # Dict[.., ..] might be nested
    if generic_of(vtype) == dict:
        dict_ktype, dict_vtype = generic_over(vtype)
        if dict_ktype not in ALLOWED_DICT_KEY_TYPES and not dict_ktype == Any:
            raise Exception(
                f"The dictionary '{name}' cannot be annotated with type "
                f"'{dict_ktype}' as only {ALLOWED_DICT_KEY_TYPES} are allowed")
        # value-types must be checked deeply
        assert_type_annotation_allowed(name, dict_vtype)
        return

    # if not handled already let all allowed types pass
    if vtype in ALLOWED_TYPE_ANNOTATIONS:
        return

    # if annotated with a class then it is of type 'type' eg.
    # class A:
    #   block: Block
    if type(vtype) == type:
        return

    raise Exception(f"Unsupported type '{vtype.__class__}' of key '{name}'")

def check_default(vname: str, vtype: Type, default: DefaultVarType) -> OptionalVar:
    # type check the default before proceeding
    if not isinstance(default, VAR_DEFAULT_TYPES):
        raise Exception(
            f"Defaults must be of type {VAR_DEFAULT_TYPES}!! "
            f"You set {vname} to {type(default)}")

    # type check the default before proceeding
    # this only works for non factory functions as it would
    # be considered unexpected behavior if the provided default
    # function is called during class definition
    if not inspect.isfunction(default):
        resolve_type(f"Default of {vname}", default, vtype)

    return OptionalVar(vtype, default)

#########################
# Resolvers
#########################
class PrimitiveResolver(Resolver):
    def __init__(self, target: Type):
        self.target = target
    def is_responsible(self, value: Any, target: Type) -> bool:
        return target == self.target
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        if not isinstance(value, target):
            raise WrongType(name, value, target)
        return value

class DictResolver(Resolver):
    def is_responsible(self, value: Any, target) -> bool:
        return is_generic_dict(target)
    def resolve(self, name: str, value: Any, target) -> Any:
        if not isinstance(value, dict):
            raise WrongType(name, value, target)

        dict_ktype, dict_vtype = generic_over(target)

        result = dict()
        for k, v in value.items():
            if not isinstance(k, ALLOWED_DICT_KEY_TYPES):
                raise Exception(
                    f"Key '{k}' was expected to be a primitive in '{name}'")

            resolve_type(str(k), k, dict_ktype)
            result[k] = resolve_type(name, v, dict_vtype)

        return result

class ListResolver(Resolver):
    def is_responsible(self, value: Any, target: Type) -> bool:
        return is_generic_list(target)
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        if not isinstance(value, list):
            raise WrongType(name, value, target)
        [ltype] = generic_over(target)
        return [resolve_type(name, n, ltype) for n in value]

class ClassResolver(Resolver):
    def is_responsible(self, value: Any, target: Type) -> bool:
        return not isinstance(target, PRIMITIVES) and type(target) == type
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        if not isinstance(value, dict):
            raise WrongType(name, value, target)
        return target(**value)

class NoneResolver(Resolver):
    def is_responsible(self, value: Any, target: Type) -> bool:
        return value is None
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        return value

class AnyResolver(Resolver):
    def is_responsible(self, value: Any, target: Type) -> bool:
        return target == Any
    def resolve(self, name: str, value: Any, target: Type) -> Any:
        return value

RESOLVERS = [
    NoneResolver(),
    AnyResolver(),

    PrimitiveResolver(int),
    PrimitiveResolver(float),
    PrimitiveResolver(str),
    PrimitiveResolver(bool),

    ClassResolver(),

    ListResolver(),
    DictResolver(),
]

def resolve_type(name: str, value: Any, vtype: Type) -> Any:
    """
    Ensures that value is of the expected type.
    The value might be recursivly resolved if it is nested.
    """

    # instead of a long if elif else structure
    # ask if threre is a resolver responsible and
    # let it resolve the value. The predicate to
    # test if a resolver is responsible can be
    # more complicated than just to check the vtype
    for res in RESOLVERS:
        if res.is_responsible(value, vtype):
            return res.resolve(name, value, vtype)

    raise WrongType(name, value, vtype)

##########################
# Exported
#########################

class WrongType(Exception):
    TEMPLATE = "Wrong type '{actual}' with value '{value}' for key '{key}'. " +\
               "Expected '{target}'."
    def __init__(self, key: str, value: Any, target: Type) -> None:
        self.msg = WrongType.TEMPLATE.format(
            key=key,
            value=value,
            actual=getattr(type(value), '__name__', type(value)),
            target=target,
        )
        super().__init__(self)
    def __str__(self):
        return self.msg

class UnknownArgument(Exception):
    TEMPLATE = "Unknown argument '{value}' of type '{actual}' with key '{key}'."
    def __init__(self, key: str, value: Any) -> None:
        self.msg = UnknownArgument.TEMPLATE.format(
            key=key,
            value=value,
            actual=getattr(type(value), '__name__', type(value)),
        )
        super().__init__(self)
    def __str__(self):
        return self.msg

class MissingRequiredArgument(Exception):
    TEMPLATE = "Missing required argument '{key}' for '{parent}'"
    def __init__(self, key: str, parent: Type) -> None:
        self.msg = MissingRequiredArgument.TEMPLATE.format(
            key=key,
            parent=parent,
        )
        super().__init__(self)
    def __str__(self):
        return self.msg

class UnsupportedType(Exception):
    TEMPLATE = "Value of type '{type}' is not supported"
    def __init__(self, value: Any) -> None:
        self.msg = UnsupportedType.TEMPLATE.format(
            type=getattr(type(value), '__name__', type(value)),
        )
        super().__init__(self)
    def __str__(self):
        return self.msg

class ValueNotAnOption(Exception):
    TEMPLATE = "Value of type '{type}' with value '{value}' is not an option. " +\
                "Choose on of: {options}"
    def __init__(self, value: Any, options: List) -> None:
        self.msg = UnsupportedType.TEMPLATE.format(
            type=getattr(type(value), '__name__', type(value)),
            value=value,
            options=options
        )
        super().__init__(self)
    def __str__(self):
        return self.msg

def asdict(inst):
    names = [name for name, _ in get_annotations(inst.__class__)]
    return {name: getattr(inst, name) for name in names if hasattr(inst, name)}

def yamlfield(alias: str = None,
              default: DefaultVarType = None,
              options: List = None
            ) -> YamlField:
    """
    Just like dataclasses.field does yamlfield provide a way to handle more
    special cases like using a different name in the yaml
    """
    if default is not None and options is not None:
        if default not in options:
            raise ValueNotAnOption(default, options)

    # keep the internal representation hidden from the user
    return YamlField(alias=alias, default=default, options=options)

def yamlcls(cls=None, ignore_missing: bool = False, ignore_unknown: bool = False):
    """ EVERYTHING NEEES A TYPE HINT!! """
    def _create_init(cls,
                     required: Dict[str, RequiredVar],
                     optional: Dict[str, OptionalVar],
                     alias: Dict[str, str],
                     options: Dict[str, List],
                    ):
        def _chose_init_source(args: List, kwargs: Dict) -> Dict[Any, Any]:
            # guard against miss-usage
            if min(1, len(args)) + min(1, len(kwargs)) > 1:
                raise Exception(
                    f"Init '{cls.__name__}' with either with a dict or kwargs!")

            # one dict was provided?
            if len(args) > 0:
                if not isinstance(args[0], dict):
                    raise Exception(
                        f"Init '{cls.__name__}' with either with a dict or kwargs! "
                        f"You passed {type(args[0]).__name__}.")
                return args[0]

            return kwargs


        def _init(self, *args, **kwargs):
            init_dict = _chose_init_source(args, kwargs)

            rset = {name: False for name in required}
            oset = {name: False for name in optional}

            for k, v in init_dict.items():
                # translate the yaml name to the class name
                if k not in alias:
                    if not ignore_unknown:
                        raise UnknownArgument(k, v)
                    continue

                # translate yaml-name to internal one
                k, yamlname = alias[k], k

                # determine what dict we are using for other operations
                source = None
                if k in rset:
                    rset[k] = True
                    source = required
                elif k in oset:
                    oset[k] = True
                    source = optional
                else:
                    raise Exception(
                        f"Programming error... {k} should be either required "
                        f"or optional")

                if not isinstance(v, (str, int, float, list, dict)):
                    raise UnsupportedType(v)

                if k in options:
                    if v not in options[k]:
                        raise ValueNotAnOption(v, options[k])

                v = resolve_type(yamlname, v, source[k].type)
                setattr(self, k, v)

            # ensure that all required variables are set
            for k, isset in rset.items():
                if not isset and not ignore_missing:
                    raise MissingRequiredArgument(k, cls.__name__)

            # fill defaults for unset variables
            for k, isset in oset.items():
                if isset:
                    continue

                default = optional[k].default
                if inspect.isfunction(default):
                    default = default()
                    resolve_type(f"Default of {k}", default, optional[k].type)
                    setattr(self, k, default)
                else:
                    setattr(self, k, default)

        return _init

    def _create_to_str(cls,
                       required: Dict[str, RequiredVar],
                       optional: Dict[str, OptionalVar]):
        def _str(self):
            s = f"{cls.__name__}("
            args = itertools.chain(required.keys(), optional.keys())
            args = filter(lambda name: hasattr(self, name), args)
            s += ", ".join(map(lambda name: f"{name}={getattr(self, name)}", args))
            s += ")"
            return s
        return _str

    def wrap(cls):
        """ Create __init__ and __str__ based on annotations of the class """

        required: Dict[str, RequiredVar] = dict()
        optional: Dict[str, OptionalVar] = dict()
        alias: Dict[str, str] = dict() # yaml-name to class-name
        options: Dict[str, List] = dict()

        missing = "__MISSING__"

        for vname, vtype in get_annotations(cls):
            assert_type_annotation_allowed(vname, vtype)

            # resolve default and classify as req or opt
            default = getattr(cls, vname, missing)
            # no default given
            if default == missing:
                required[vname] = RequiredVar(vtype)
                alias[vname] = vname
            # yamlfield was used so this field is special
            elif isinstance(default, YamlField):
                # default value handling
                if default.default is None:
                    required[vname] = RequiredVar(vtype)
                else:
                    optional[vname] = check_default(vname, vtype, default.default)
                    alias[vname] = vname

                if default.options is not None:
                    resolve_type(f"Options of {cls.__name__}.{vname}", default.options, List[vtype])
                    options[vname] = default.options

                # alias handling
                if default.alias is not None:
                    alias[default.alias] = vname
                else:
                    alias[vname] = vname

            # normal optional argument
            else:
                optional[vname] = check_default(vname, vtype, default)
                alias[vname] = vname

        setattr(cls, "__init__", _create_init(cls, required, optional, alias, options))
        setattr(cls, "__str__", _create_to_str(cls, required, optional))
        return cls

    return wrap if cls is None else wrap(cls)

__all__ = [
    "yamlcls",
    "asdict",
    "yamlfield",
    "WrongType",
    "UnknownArgument",
    "MissingRequiredArgument",
]
