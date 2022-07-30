// SPDX-FileCopyrightText: 2022 wingdeans <wingdeans@protonmail.com>
// SPDX-License-Identifier: LGPL-3.0-only

#pragma SWIG nowarn=451,473

// Buffers
%include <pybuffer.i>

%define %buffer_len_activate(TYPEMAP, SIZE)
%pybuffer_mutable_binary(unsigned char *buf, unsigned long long len);
%enddef

%define %buffer_len_deactivate(TYPEMAP, SIZE)
%typemap(in) (unsigned char *buf, unsigned long long len);
%enddef

// CArrays
%include <carrays.i>
%inline %{
    typedef char* String;
%}
%array_class(String, Array_String);

// Python plugin
%pythoncode %{
    core = None
%}

// Directors
%feature("director") CmdDirector;
%inline %{
struct CmdDirector {
    virtual bool run(RzCore *core, int argc, const char **argv) {
        throw Swig::DirectorPureVirtualException("run");
    }
    CmdDirector() {};
    virtual ~CmdDirector() {};
};
%}

%{
#include <unordered_map>

static auto SWIGCmds = std::unordered_map<std::string, std::pair<RzCmdDesc*, CmdDirector*> >();

RzCmdStatus SWIG_Cmd_run(RzCore *core, int argc, const char **argv) {
    std::string cmd(argv[0]);
    bool result = SWIGCmds.at(cmd).second->run(core, argc, argv);
    return result ? RZ_CMD_STATUS_OK : RZ_CMD_STATUS_ERROR;
}

void rz_swig_cmd_desc_help_free(const RzCmdDescHelp *help) {
    free((char*) help->summary);
    free((char*) help->description);
    free((char*) help->args_str);
    free((char*) help->usage);
    free((char*) help->options);
    if (help->details) {
        rz_cmd_desc_details_free((RzCmdDescDetail*) help->details);
    }

    for (const RzCmdDescArg *arg = help->args; arg && arg->name; ++arg) {
        free((char*) arg->name);
        free((char*) arg->default_value);
    }
    free((RzCmdDesc*) help->args);
}
%}

%array_class(RzCmdDescArg, Array_RzCmdDescArg);

// Python arg annotations
%pythoncode %{
    class RzNumArg: pass
    class RzFilenameArg: pass
%}

