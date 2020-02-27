main 
{
    *host =  ""
    *context = ""
    application_context_from_input(*host,*context,"*incoll","*data")
    if (*host != "") 
    {
        irods_policy_list_applications (*host, *context , *l) 
        writeLine("stdout",*l)
        *id = '' 
        *err = '' 
        *app_name = full_application_name_from_glob (*app, *l)
        writeLine("stdout","\nInfo: running container from config: '*app' -> '*app_name'")
        irods_policy_run_application (*host, *context , '', '*outcoll', '{"DEGREES_ROTATION":"10"}',
                                     '*app_name' ,*id,*err) 
        writeLine("stdout",'id=[*id]')                             
        if (*err != '') { writeLine("stdout",'In application launch: [*err]') }
        writeLine("stdout",'ctx=[*context]')

        if (*id != "") {  # if it's a detached container...
            # via POLL, make sure the products are registered upon exit
            delay("<PLUSET>1s</PLUSET>") { irods_policy_poll_application(*host,*context, *id, *attr_out, *status_out, "600") }
            # Detect by our naming convention if it's a Notebook app, and display the URL when available
            if (*app_name like ("*"++"_notebook.json")) {
                for (*t = 0; *t < *max_url_wait; *t=*t+1) { # maximum url wait is in seconds
                    *exitcode = "" ; *cmd_stdout = "" 
                    irods_policy_exec_command_in_application (*host, *context ,*id, "jupyter notebook list", *exitcode, *cmd_stdout)
                    *url = detect_notebook_URL (*cmd_stdout)
                    if (*url != "") { writeLine ("stdout", "Jupyter Notebook running at [ *url ]") ; break }
                    if (*exitcode == "") { writeLine("stderr", "ERROR in container exec [[\n*cmd_stdout\n]]"); break }
                    msiSleep("1","0")
                }
            }
        }
    }
}

detect_notebook_URL( *output_buffer)
{
  *url = ""
  msiStrlen(*output_buffer,*initial_length)
  *buf = trimr(*output_buffer, " :: ")
  msiStrlen(*buf,*clipped_length)
  if (*clipped_length != *initial_length) { 
    *result = triml(*buf, "http")
    *url = "http" ++ *result
  }
  *url
}


#
#  Utility functions / rules
#

kvpair_to_json(*x)  
{   
    *json = "{\n"
    *sep = " " 
    foreach (*n in *x) {
        *json = *json ++ '*sep "*n": "' ++ *x.*n ++ '"'
        *sep = ",\n "
    }
    *json = *json ++ "\n}"
    *json
}

full_application_name_from_glob (*app_sel, *app_lst)
{
   *app_path = ""
   msiSubstr(*app_sel, '0', '2' , *first2)
   if (*first2 == '*/') {
       foreach( *x in *app_lst) { 
           if (*x like *app_sel)  { *app_path = *x; break; }
       }
   }
   if (*app_path != "") {*app_path} else {*app_sel}
}

application_context_from_input ( *host, *context, *input_coll_pattern, *input_data_basename)
{
    *x.compute_host = ""
    foreach ( *d in select COLL_NAME, DATA_NAME, RESC_LOC ,RESC_NAME
                     where COLL_NAME like '*input_coll_pattern'
                     and   DATA_NAME = '*input_data_basename')
    {
        *x.compute_host = *d.RESC_LOC
        *x.compute_resource = *d.RESC_NAME
        *x.input_collection_hint = *d.COLL_NAME
        *x.Env__data_set = *d.DATA_NAME 
        *host = *x.compute_host
        *context = kvpair_to_json ( *x )
        break
    }
}

INPUT *data="square.img.csv", *incoll="%", *outcoll=$"/tempZone/home/alice/output", *app=$"*/sobel_notebook.json", *max_url_wait=10
OUTPUT ruleExecOut
