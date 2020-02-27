#
# Native rule base for calling into irods docker application API
#

irods_policy_list_applications (*host, *config, *lst) 
{
    if (*config == "") { *config = "{}" }
    *rlst = ""
    remote (*host,"") {
        irods_container_Impl__list_applications ( *config , *rlst )
    }
    *lst = eval("list" ++ *rlst) 
}

irods_policy_poll_application (*host, *context, *id, *attr_out, *status_out, *loop_seconds) 
{
    *attr_out = ""
    *status_out = ""
    remote(*host,"") {
        irods_container_Impl__poll_application(*context, *id, *attr_out, *status_out, *loop_seconds)
    }
}

irods_policy_run_application (*host, *context, *input, *output, *extra_env, *application, *id, *errmsg) 
{
    *errmsg = ""
    *id = ""
    remote (*host,"") {
        irods_container_Impl__run_application ( *context , *input, *output, *extra_env, *application, *id, *errmsg)
    }
}

irods_policy_exec_command_in_application (*host, *context, *id, *command, *returncode, *cmd_output ) 
{
    *returncode = ""
    *cmd_output = ""
    remote (*host,"") {
        irods_container_Impl__exec_command_in_application (*context, *id, *command, *returncode, *cmd_output )
    }
}
