"""
SPDX-FileCopyrightText: 2022 wingdeans <wingdeans@protonmail.com>
SPDX-License-Identifier: LGPL-3.0-only

Specifies the rizin SWIG %module
"""

from typing import List, Dict, OrderedDict, Set, Optional, TextIO, TYPE_CHECKING

from clang.cindex import SourceRange
from clang.wrapper import Cursor, CursorKind, Type, TypeKind

from writer import DirectWriter

if TYPE_CHECKING:
    from module_class import ModuleClass
    from module_generic import ModuleGeneric
    from module_director import ModuleDirector
    from header import Header


class Module:
    """
    Represents a SWIG %module
    """

    headers: Set["Header"]
    classes: List["ModuleClass"]

    generics: OrderedDict[str, "ModuleGeneric"]
    # maps struct name -> generic name (eg. rz_list_t -> RzList)
    generic_mappings: Dict[str, str]

    directors: List["ModuleDirector"]
    enable_directors: bool

    def __init__(self) -> None:
        self.headers = set()
        self.classes = []
        self.generics = OrderedDict()
        self.generic_mappings = {}
        self.directors = []

    def get_generic_name(self, type_: Type) -> Optional[str]:
        """
        Get generic name from cursor type (eg. rz_list_t -> RzList)

        If void, return "void"
        If not a generic, return None
        """
        while type_.kind == TypeKind.POINTER:
            type_ = type_.get_pointee()

        if type_.kind == TypeKind.VOID:
            return "void"

        struct_name = type_.get_canonical().get_declaration().spelling
        if struct_name in self.generic_mappings:
            return self.generic_mappings[struct_name]

        return None

    def add_generic_specialization(self, cursor: Cursor, generic_name: str) -> str:
        """
        Extract generic /*<type>*/ comment and add to generic_specializations
        """
        assert (
            cursor.kind == CursorKind.FIELD_DECL
            or cursor.kind == CursorKind.FUNCTION_DECL
            or cursor.kind == CursorKind.PARM_DECL
        )

        typeref = next(
            child
            for child in cursor.get_children()
            if child.kind == CursorKind.TYPE_REF
        )
        src_range = SourceRange.from_locations(typeref.extent.end, cursor.location)
        token = next(cursor.translation_unit.get_tokens(extent=src_range)).spelling

        if not token.startswith("/*<") or not token.endswith(">*/"):
            raise Exception(
                f"{generic_name} at {cursor.location} lacks /*<type>*/ annotation"
            )
        name = token[3:-3]
        if name.startswith("const "):
            name = name[len("const ") :]

        # Add specialization
        generic = self.generics[generic_name]

        if generic.pointer:
            if name[-1] != "*":
                raise Exception(
                    f"Specializations of generic {generic.name} should have a pointer, "
                    f"but specialization at {cursor.location} does not"
                )

            if name[-2] != " ":
                raise Exception(
                    f"Specialization at {cursor.location}"
                    "lacks space between type and pointer"
                )
            name = name[:-2]

        generic.specializations.add(name)

        return name

    def stringify_decl(
        self,
        cursor: Cursor,
        type_: Type,
        *,
        name: Optional[str] = None,
        generic: bool = False,
    ) -> str:
        """
        Combine a name and a type to form a declaration string
        eg. (anArray, int[10]) -> "int anArray[10]"
        eg. (aFunctionPointer, (*int)(int a, int b)) -> "int (*aFunctionPointer)(int a, int b)"

        If the type is generic, get the inner type from the comment
        and generate the correct specialization

        If being called from a generic %define, use ##TYPE as the inner type
        """

        # Get generic typename if applicable
        generic_name = self.get_generic_name(type_)
        type_name = None
        if generic_name == "void":
            if generic:
                type_name = "TYPE"
        elif generic_name:  # Is generic type?
            if generic:
                type_name = f"{generic_name}_##TYPE"
            else:
                specialization = self.add_generic_specialization(cursor, generic_name)
                type_name = f"{generic_name}_{specialization}"

        name = name or cursor.spelling

        # Unravel pointers
        while type_.kind == TypeKind.POINTER:
            type_ = type_.get_pointee()
            name = "*" + name

        # Reorder array and function pointer declarations
        if type_.kind == TypeKind.CONSTANTARRAY:
            name = f"{name}[{type_.element_count}]"
            type_ = type_.element_type
        elif type_.kind == TypeKind.INCOMPLETEARRAY:
            name = f"{name}[]"
            type_ = type_.element_type
        elif type_.kind == TypeKind.FUNCTIONPROTO:
            args = ", ".join(arg.spelling for arg in type_.argument_types())
            name = f"({name})({args})"
            type_ = type_.get_result()
        elif type_.kind == TypeKind.BOOL:
            type_name = "bool"  # _Bool -> bool

        return f"{type_name or type_.spelling} {name}"

    def write(self, output: TextIO) -> None:
        """
        Write self to an opened file or stdout
        """

        writer = DirectWriter(output)
        if self.enable_directors:
            writer.line("%module(directors=1) rizin")
        else:
            writer.line("%module rizin")

        # Headers
        writer.line("%{")
        for header in self.headers:
            writer.line(f"#include <{header.name}>")
        writer.line("%}")

        # Typemaps
        writer.line("%include <rizin_lib.i>")

        for generic in self.generics.values():
            generic.merge(writer)

        # Deprecation warning settings
        writer.line(
            "%inline %{",
            "bool rizin_warn_deprecate = true;",
            "bool rizin_warn_deprecate_instructions = true;",
            "%}",
        )
        writer.line(
            "%{",
            "void rizin_try_warn_deprecate(const char *name, const char *c_name) {",
            "    if (rizin_warn_deprecate) {",
            '        printf("Warning: `%s` calls deprecated function `%s`\\n", name, c_name);',
            "        if (rizin_warn_deprecate_instructions) {",
            '            puts("To disable this warning, set rizin_warn_deprecate to false");',
            '            puts("The way to do this depends on the SWIG language being used");',
            '            puts("For python, do `rizin.cvar.rizin_warn_deprecate = False`");',
            "        }",
            "    }",
            "}",
            "%}",
        )

        for cls in self.classes:
            cls.merge(writer)

        if self.enable_directors:
            for director in self.directors:
                director.merge(writer)


# The rizin %module is the only SWIG module
rizin = Module()
