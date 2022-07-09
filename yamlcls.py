import itertools
import inspect
from typing import Any, Callable, Dict, List, Union, Type

__all__ = ["yamlcls", "asdict", "yamlfield"]

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
    def __init__(self, alias: str = None, default: DefaultVarType = None):
        self.alias = alias
        self.default = default

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


def resolve_type(name: str, value: Any, vtype: Type) -> Any:
    """
    Ensures that value is of the expected type.
    The value might be recursivly resolved if it is nested.
    """
    if value is None or vtype == Any:
        return value

    # Check correctness of primitives
    if isinstance(value, PRIMITIVES) and vtype in PRIMITIVES and isinstance(value, vtype):
        return value

    # Resolve a custom type.
    # Meaning we get a dict but expect something custom
    if isinstance(value, dict) \
            and not isinstance(vtype, PRIMITIVES) \
            and type(vtype) == type:
        return vtype(**value)

    # check a typed list (a: List[str])
    if isinstance(value, list) and is_generic_list(vtype):
        [ltype] = generic_over(vtype)
        return [resolve_type(name, n, ltype) for n in value]

    # check a typed dict (a: Dict[str, str])
    if isinstance(value, dict) and is_generic_dict(vtype):
        dict_ktype, dict_vtype = generic_over(vtype)

        result = dict()
        for k, v in value.items():
            if not isinstance(k, ALLOWED_DICT_KEY_TYPES):
                raise Exception(
                    f"Key '{k}' was expected to be a primitive in '{name}'")

            resolve_type(str(k), k, dict_ktype)
            result[k] = resolve_type(name, v, dict_vtype)

        return result

    raise Exception(
        f"Expected value of type '{vtype.__name__}' but got '{value}' "
        f"({type(value).__name__}) for key '{name}'")

##########################
# Exported
#########################

def asdict(inst):
    names = [name for name, _ in get_annotations(inst.__class__)]
    return {name: getattr(inst, name) for name in names if hasattr(inst, name)}

def yamlfield(alias: str = None, default: DefaultVarType = None):
    """
    Just like dataclasses.field does yamlfield provide a way to handle more
    special cases like using a different name in the yaml
    """
    # keep the internal representation hidden from the user
    return YamlField(alias=alias, default=default)

def yamlcls(cls=None, ignore_missing: bool = False, ignore_unknown: bool = False):
    """ EVERYTHING NEEES A TYPE HINT!! """
    def _create_init(cls,
                     required: Dict[str, RequiredVar],
                     optional: Dict[str, OptionalVar],
                     alias: Dict[str, str]):
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
                        raise Exception(
                            f"Unknown argument '{v}' of type '{type(v)}' for "
                            f"'{cls.__name__}' with key '{k}'")
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
                    raise Exception(f"Value of type '{type(v)}' is not supported")

                v = resolve_type(yamlname, v, source[k].type)
                setattr(self, k, v)

            # ensure that all required variables are set
            for k, isset in rset.items():
                if not isset and not ignore_missing:
                    raise Exception(
                        f"Missing required argument '{k}' for "
                        f"'{cls.__name__}'")

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
                if default.default == None:
                    required[vname] = RequiredVar(vtype)
                else:
                    # type check the default before proceeding
                    resolve_type(f"Default of {vname}", default.default, vtype)
                    optional[vname] = OptionalVar(vtype, default.default)

                # alias handling
                if default.alias != None:
                    alias[default.alias] = vname
                else:
                    alias[vname] = vname

            # normal optional argument
            else:
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

                optional[vname] = OptionalVar(vtype, default)
                alias[vname] = vname

        setattr(cls, "__init__", _create_init(cls, required, optional, alias))
        setattr(cls, "__str__", _create_to_str(cls, required, optional))
        return cls

    return wrap if cls is None else wrap(cls)
